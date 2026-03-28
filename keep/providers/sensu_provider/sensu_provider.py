"""
SensuProvider is a class that implements the BaseProvider interface for Sensu Go.

Sensu Go is an open-source monitoring and observability pipeline that provides
automated infrastructure monitoring, health checking, and alerting.

Supports:
  - Pull mode: query Sensu Go REST API for active events (non-OK)
  - Push mode: receive Sensu Go events via HTTP handler webhook
"""

import dataclasses
import datetime
import logging
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SensuProviderAuthConfig:
    """
    Sensu Go authentication configuration.

    Supports API key (preferred) or username/password basic auth.
    """

    sensu_host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Sensu Go API base URL",
            "hint": "http://sensu.example.com:8080",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go API key (preferred over username/password)",
            "hint": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "sensitive": True,
        },
        default="",
    )

    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go username for basic auth",
            "hint": "admin",
            "sensitive": False,
        },
        default="",
    )

    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go password for basic auth",
            "hint": "P@ssw0rd",
            "sensitive": True,
        },
        default="",
    )

    namespace: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go namespace to pull events from",
            "hint": "default",
            "sensitive": False,
        },
        default="default",
    )

    pull_all_namespaces: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Pull events from all namespaces (cluster-wide)",
            "hint": "false",
            "sensitive": False,
        },
        default=False,
    )


class SensuProvider(BaseProvider):
    """
    Manage Sensu Go events in Keep.

    Pull mode: queries the Sensu Go REST API for non-OK events in a namespace
    (or cluster-wide). Supports both API-key and basic-auth.

    Push mode: receives raw Sensu event payloads via an HTTP handler configured
    in Sensu, e.g. a mutator + handler that POSTs to Keep's webhook endpoint.
    """

    PROVIDER_DISPLAY_NAME = "Sensu Go"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="events:get",
            description="Read events from the Sensu Go API",
            mandatory=True,
            documentation_url="https://docs.sensu.io/sensu-go/latest/api/core/events/",
        ),
    ]

    FINGERPRINT_FIELDS = ["entity", "check"]

    # Sensu status codes -> Keep severity
    # 0 = OK (passing)  -> INFO / RESOLVED
    # 1 = WARNING       -> WARNING
    # 2 = CRITICAL      -> CRITICAL
    # ≥3 = UNKNOWN      -> HIGH (treated as unknown severity)
    SEVERITY_MAP: dict[int, AlertSeverity] = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
    }

    # Sensu event state -> Keep status
    STATE_MAP: dict[str, AlertStatus] = {
        "passing": AlertStatus.RESOLVED,
        "failing": AlertStatus.FIRING,
        "flapping": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None

    def dispose(self) -> None:
        pass

    def validate_config(self) -> None:
        """Validate provider authentication config."""
        self.authentication_config = SensuProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.api_key and not (
            self.authentication_config.username and self.authentication_config.password
        ):
            raise ValueError(
                "Provide either 'api_key' or both 'username' and 'password'."
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that we can reach the Sensu Go API."""
        validated: dict[str, bool | str] = {}
        try:
            self._get_events(limit=1)
            validated["events:get"] = True
        except Exception as exc:
            self.logger.warning(
                "Failed to validate Sensu scopes", extra={"error": str(exc)}
            )
            validated["events:get"] = str(exc)
        return validated

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _get_auth_headers(self) -> dict[str, str]:
        """Return HTTP headers for authenticating against the Sensu API."""
        if self.authentication_config.api_key:
            return {"Authorization": f"Key {self.authentication_config.api_key}"}
        if not self._access_token:
            self._access_token = self._obtain_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _obtain_access_token(self) -> str:
        """Exchange username/password for a bearer access token."""
        url = urljoin(str(self.authentication_config.sensu_host), "/auth")
        response = requests.get(
            url,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get("access_token", "")
        if not token:
            raise ValueError("Sensu /auth returned no access_token")
        return token

    def _api_get(self, endpoint: str, params: Optional[dict] = None) -> list | dict:
        """Perform an authenticated GET request against the Sensu API."""
        url = urljoin(str(self.authentication_config.sensu_host), endpoint)
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Pull mode
    # ------------------------------------------------------------------

    def _get_events(self, limit: Optional[int] = None) -> list[dict]:
        """Fetch raw Sensu events from the API."""
        if self.authentication_config.pull_all_namespaces:
            endpoint = "/api/core/v2/events"
        else:
            ns = self.authentication_config.namespace or "default"
            endpoint = f"/api/core/v2/namespaces/{ns}/events"

        params: dict = {}
        if limit:
            params["limit"] = limit

        result = self._api_get(endpoint, params)
        return result if isinstance(result, list) else []

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch and format Sensu events as Keep AlertDtos (non-OK only)."""
        raw_events = self._get_events()
        alerts: list[AlertDto] = []
        for event in raw_events:
            check = event.get("check", {})
            status_code = check.get("status", 0)
            # Only surface non-OK events as alerts
            if status_code == 0:
                continue
            try:
                alert = self._event_to_alert_dto(event)
                alerts.append(alert)
            except Exception:
                self.logger.exception(
                    "Failed to parse Sensu event",
                    extra={"event_id": event.get("id")},
                )
        return alerts

    # ------------------------------------------------------------------
    # Push mode
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Convert a raw Sensu event payload (push/webhook) to an AlertDto.

        Sensu handlers can POST events to Keep via an HTTP handler.
        The payload structure mirrors the Sensu event object:
        https://docs.sensu.io/sensu-go/latest/observability-pipeline/observe-events/events/
        """
        return SensuProvider._event_to_alert_dto_static(event)

    # ------------------------------------------------------------------
    # Shared conversion logic
    # ------------------------------------------------------------------

    def _event_to_alert_dto(self, event: dict) -> AlertDto:
        return SensuProvider._event_to_alert_dto_static(event)

    @staticmethod
    def _event_to_alert_dto_static(event: dict) -> AlertDto:
        """
        Convert a Sensu event dict to an AlertDto.
        This is the canonical conversion used by both pull and push paths.
        """
        check = event.get("check", {})
        entity = event.get("entity", {})
        event_metadata = event.get("metadata", {})

        check_meta = check.get("metadata", {})
        entity_meta = entity.get("metadata", {})

        check_name = check_meta.get("name", "unknown")
        entity_name = entity_meta.get("name", "unknown")
        namespace = event_metadata.get("namespace") or check_meta.get(
            "namespace", "default"
        )
        event_id = event.get("id") or f"{entity_name}:{check_name}"

        status_code = check.get("status", 0)
        state = check.get("state", "failing")
        is_silenced = check.get("is_silenced", False)

        # Severity
        severity = SensuProvider.SEVERITY_MAP.get(status_code, AlertSeverity.HIGH)

        # Status
        if is_silenced:
            status = AlertStatus.SUPPRESSED
        elif status_code == 0:
            status = AlertStatus.RESOLVED
        else:
            status = SensuProvider.STATE_MAP.get(state, AlertStatus.FIRING)

        # Timestamp
        ts = event.get("timestamp", 0)
        if ts:
            last_received = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc
            )
        else:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc)

        # Labels / enrichment
        entity_labels = dict(entity_meta.get("labels") or {})
        check_labels = dict(check_meta.get("labels") or {})
        labels = {**entity_labels, **check_labels}

        environment = labels.pop("environment", None) or labels.pop("env", namespace)
        service = labels.pop("service", None) or entity_name

        output = (check.get("output") or "").strip()
        description = output or check_name

        # Sensu web-UI URL (best-effort; requires sensu_host)
        # When called statically we don't have the host, so leave url blank.
        url = ""

        return AlertDto(
            id=event_id,
            name=check_name,
            description=description,
            message=description,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["sensu"],
            environment=environment,
            service=service,
            labels=labels,
            url=url,
            # Sensu-specific extra fields
            entity=entity_name,
            check=check_name,
            namespace=namespace,
            status_code=status_code,
            occurrences=check.get("occurrences", 1),
            is_silenced=is_silenced,
            hostname=entity.get("system", {}).get("hostname", entity_name),
            pushed=bool(event.get("_pushed", False)),
        )


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    provider_config = {
        "authentication": {
            "sensu_host": os.environ["SENSU_HOST"],
            "api_key": os.environ.get("SENSU_API_KEY") or "",
            "username": os.environ.get("SENSU_USERNAME") or "",
            "password": os.environ.get("SENSU_PASSWORD") or "",
            "namespace": os.environ.get("SENSU_NAMESPACE") or "default",
        },
    }

    from keep.providers.providers_factory import ProvidersFactory

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="sensu",
        provider_type="sensu",
        provider_config=provider_config,
    )
    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} active alerts")
    for alert in alerts:
        print(f"  {alert.name} [{alert.severity}] {alert.status}")
