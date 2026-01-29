"""
Sensu Go Provider is a class that allows to ingest/digest data from Sensu Go.

Sensu Go is an open-source monitoring and observability pipeline that provides
automated infrastructure monitoring, health checking, and alerting.
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
    """

    sensu_host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Sensu Go API URL",
            "hint": "http://sensu.example.com:8080",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go API Key",
            "hint": "API key for authentication (preferred over basic auth)",
            "sensitive": True,
        },
        default="",
    )
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go Username",
            "hint": "Username for basic auth (if not using API key)",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go Password",
            "hint": "Password for basic auth (if not using API key)",
            "sensitive": True,
        },
        default="",
    )
    namespace: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu Go Namespace",
            "hint": "Namespace to query events from (default: 'default')",
            "sensitive": False,
        },
        default="default",
    )
    pull_all_namespaces: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Pull events from all namespaces",
            "hint": "If enabled, ignores the namespace field and pulls from all namespaces",
            "sensitive": False,
        },
        default=False,
    )


class SensuProvider(BaseProvider):
    """
    Pull alerts/events from Sensu Go into Keep.

    Sensu Go is an open-source monitoring and observability pipeline that provides
    automated infrastructure monitoring, health checking, and alerting.
    """

    PROVIDER_DISPLAY_NAME = "Sensu Go"
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="events:read",
            description="Read events from Sensu Go API",
            mandatory=True,
            documentation_url="https://docs.sensu.io/sensu-go/latest/api/core/events/",
        ),
    ]

    # Sensu status codes: 0=OK, 1=WARNING, 2=CRITICAL, >2=UNKNOWN
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,      # OK - passing
        1: AlertSeverity.WARNING,   # WARNING
        2: AlertSeverity.CRITICAL,  # CRITICAL
    }

    # State mapping
    STATUS_MAP = {
        "passing": AlertStatus.RESOLVED,
        "failing": AlertStatus.FIRING,
        "flapping": AlertStatus.FIRING,
    }

    FINGERPRINT_FIELDS = ["entity", "check"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Sensu Go provider.
        """
        self.authentication_config = SensuProviderAuthConfig(
            **self.config.authentication
        )
        # Validate that we have either API key or username/password
        if not self.authentication_config.api_key and not (
            self.authentication_config.username and self.authentication_config.password
        ):
            raise ValueError(
                "Either 'api_key' or both 'username' and 'password' must be provided"
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that we can access the Sensu Go API.
        """
        validated_scopes = {}
        try:
            # Try to fetch events to validate connectivity and permissions
            self._get_events(limit=1)
            validated_scopes["events:read"] = True
        except Exception as e:
            self.logger.warning(
                "Failed to validate Sensu scopes",
                extra={"error": str(e)},
            )
            validated_scopes["events:read"] = str(e)
        return validated_scopes

    def _get_auth_headers(self) -> dict:
        """
        Get authentication headers for API requests.
        """
        if self.authentication_config.api_key:
            return {"Authorization": f"Key {self.authentication_config.api_key}"}
        else:
            # Use basic auth to get an access token
            if not self._access_token:
                self._access_token = self._get_access_token()
            return {"Authorization": f"Bearer {self._access_token}"}

    def _get_access_token(self) -> str:
        """
        Get an access token using basic auth.
        """
        url = urljoin(str(self.authentication_config.sensu_host), "/auth")
        response = requests.get(
            url,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
        )
        response.raise_for_status()
        return response.json().get("access_token")

    def _make_request(self, endpoint: str, params: dict = None) -> dict | list:
        """
        Make an authenticated request to the Sensu Go API.
        """
        url = urljoin(str(self.authentication_config.sensu_host), endpoint)
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _get_events(self, limit: int = None) -> list[dict]:
        """
        Fetch events from Sensu Go API.
        """
        if self.authentication_config.pull_all_namespaces:
            # Use the cluster-wide events endpoint
            endpoint = "/api/core/v2/events"
        else:
            namespace = self.authentication_config.namespace or "default"
            endpoint = f"/api/core/v2/namespaces/{namespace}/events"

        params = {}
        if limit:
            params["limit"] = limit

        events = self._make_request(endpoint, params)
        return events if events else []

    def _get_severity(self, status: int) -> AlertSeverity:
        """
        Convert Sensu status code to Keep AlertSeverity.

        Sensu status codes:
        - 0: OK (passing)
        - 1: WARNING
        - 2: CRITICAL
        - >2: UNKNOWN (treated as HIGH)
        """
        if status in self.SEVERITIES_MAP:
            return self.SEVERITIES_MAP[status]
        # Status > 2 is UNKNOWN, treat as HIGH severity
        return AlertSeverity.HIGH

    def _get_status(self, state: str, is_silenced: bool = False) -> AlertStatus:
        """
        Convert Sensu state to Keep AlertStatus.
        """
        if is_silenced:
            return AlertStatus.SUPPRESSED
        return self.STATUS_MAP.get(state, AlertStatus.FIRING)

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch and convert Sensu events to Keep AlertDtos.
        Only returns non-OK events (status > 0) as alerts.
        """
        events = self._get_events()
        formatted_alerts = []

        for event in events:
            try:
                check = event.get("check", {})
                entity = event.get("entity", {})
                metadata = event.get("metadata", {})

                # Get check status - skip OK (0) events
                status_code = check.get("status", 0)
                if status_code == 0:
                    continue  # Skip passing/OK events

                # Extract relevant fields
                check_name = check.get("metadata", {}).get("name", "unknown")
                entity_name = entity.get("metadata", {}).get("name", "unknown")
                namespace = metadata.get("namespace", "default")
                event_id = event.get("id", f"{entity_name}:{check_name}")

                # Get state and silenced status
                state = check.get("state", "failing")
                is_silenced = check.get("is_silenced", False)

                # Map severity and status
                severity = self._get_severity(status_code)
                status = self._get_status(state, is_silenced)

                # Get timestamp
                timestamp = event.get("timestamp", 0)
                if timestamp:
                    last_received = datetime.datetime.fromtimestamp(
                        timestamp, tz=datetime.timezone.utc
                    ).isoformat()
                else:
                    last_received = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()

                # Get check output as description
                output = check.get("output", "")

                # Extract labels from entity
                entity_labels = entity.get("metadata", {}).get("labels", {})
                check_labels = check.get("metadata", {}).get("labels", {})
                labels = {**entity_labels, **check_labels}

                # Get environment from labels or default
                environment = labels.pop("environment", None) or labels.pop(
                    "env", namespace
                )

                # Get service from labels or entity name
                service = labels.pop("service", None) or entity_name

                # Build URL to Sensu web UI (if available)
                sensu_url = str(self.authentication_config.sensu_host).rstrip("/")
                url = f"{sensu_url}/#/events/{namespace}/{entity_name}/{check_name}"

                alert = AlertDto(
                    id=event_id,
                    name=check_name,
                    description=output.strip() if output else check_name,
                    message=output.strip() if output else check_name,
                    status=status,
                    severity=severity,
                    lastReceived=last_received,
                    source=["sensu"],
                    environment=environment,
                    service=service,
                    labels=labels,
                    url=url,
                    # Sensu-specific fields
                    entity=entity_name,
                    check=check_name,
                    namespace=namespace,
                    status_code=status_code,
                    occurrences=check.get("occurrences", 1),
                    is_silenced=is_silenced,
                    hostname=entity.get("system", {}).get("hostname", entity_name),
                )

                alert.fingerprint = self.get_alert_fingerprint(
                    alert, self.fingerprint_fields
                )
                formatted_alerts.append(alert)

            except Exception as e:
                self.logger.exception(
                    "Failed to parse Sensu event",
                    extra={
                        "event_id": event.get("id"),
                        "error": str(e),
                    },
                )
                continue

        return formatted_alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Sensu webhook event to AlertDto.
        This is used when receiving webhooks from Sensu handlers.
        """
        check = event.get("check", {})
        entity = event.get("entity", {})
        metadata = event.get("metadata", {})

        check_name = check.get("metadata", {}).get("name", "unknown")
        entity_name = entity.get("metadata", {}).get("name", "unknown")
        namespace = metadata.get("namespace", "default")
        event_id = event.get("id", f"{entity_name}:{check_name}")

        status_code = check.get("status", 0)
        state = check.get("state", "failing")
        is_silenced = check.get("is_silenced", False)

        # Map severity
        severity = SensuProvider.SEVERITIES_MAP.get(status_code, AlertSeverity.HIGH)

        # Map status
        if is_silenced:
            status = AlertStatus.SUPPRESSED
        elif status_code == 0:
            status = AlertStatus.RESOLVED
        else:
            status = SensuProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        timestamp = event.get("timestamp", 0)
        if timestamp:
            last_received = datetime.datetime.fromtimestamp(
                timestamp, tz=datetime.timezone.utc
            ).isoformat()
        else:
            last_received = datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

        output = check.get("output", "")
        entity_labels = entity.get("metadata", {}).get("labels", {})
        check_labels = check.get("metadata", {}).get("labels", {})
        labels = {**entity_labels, **check_labels}

        environment = labels.pop("environment", None) or labels.pop("env", namespace)
        service = labels.pop("service", None) or entity_name

        return AlertDto(
            id=event_id,
            name=check_name,
            description=output.strip() if output else check_name,
            message=output.strip() if output else check_name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["sensu"],
            environment=environment,
            service=service,
            labels=labels,
            entity=entity_name,
            check=check_name,
            namespace=namespace,
            status_code=status_code,
            occurrences=check.get("occurrences", 1),
            is_silenced=is_silenced,
            hostname=entity.get("system", {}).get("hostname", entity_name),
            pushed=True,
        )


if __name__ == "__main__":
    # Output debug messages
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Load environment variables
    sensu_host = os.environ.get("SENSU_HOST", "http://localhost:8080")
    api_key = os.environ.get("SENSU_API_KEY", "")
    username = os.environ.get("SENSU_USERNAME", "")
    password = os.environ.get("SENSU_PASSWORD", "")

    provider_config = {
        "authentication": {
            "sensu_host": sensu_host,
            "api_key": api_key,
            "username": username,
            "password": password,
            "namespace": "default",
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
    print(f"Found {len(alerts)} alerts")
    for alert in alerts:
        print(f"  - {alert.name}: {alert.severity} ({alert.status})")
