"""
SensuProvider is a class that provides a way to interact with Sensu Go monitoring events.
"""

import dataclasses
import datetime
import logging

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

    sensu_api_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Sensu Go API URL",
            "hint": "http://sensu-backend:8080",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Sensu Go API key",
            "hint": "Create via: sensuctl api-key grant admin",
            "sensitive": True,
        }
    )
    namespace: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sensu namespace to pull events from",
            "hint": "default",
            "sensitive": False,
        },
        default="default",
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class SensuProvider(BaseProvider):
    """Pull alerts/events from Sensu Go into Keep."""

    PROVIDER_DISPLAY_NAME = "Sensu"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="events:get",
            description="Read events from the Sensu API",
            mandatory=True,
            documentation_url="https://docs.sensu.io/sensu-go/latest/api/core/events/",
        ),
    ]

    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,       # OK
        1: AlertSeverity.WARNING,    # WARNING
        2: AlertSeverity.CRITICAL,   # CRITICAL
        127: AlertSeverity.HIGH,     # UNKNOWN
    }

    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        127: AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Sensu provider.
        """
        self.authentication_config = SensuProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {"events:get": False}
        try:
            url = f"{self.authentication_config.sensu_api_url}/api/core/v2/namespaces/{self.authentication_config.namespace}/events"
            response = requests.get(
                url,
                headers={"Authorization": f"Key {self.authentication_config.api_key}"},
                verify=self.authentication_config.verify,
                timeout=10,
            )
            if response.status_code == 200:
                scopes["events:get"] = True
            else:
                scopes["events:get"] = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as e:
            scopes["events:get"] = str(e)
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        url = f"{self.authentication_config.sensu_api_url}/api/core/v2/namespaces/{self.authentication_config.namespace}/events"
        response = requests.get(
            url,
            headers={"Authorization": f"Key {self.authentication_config.api_key}"},
            verify=self.authentication_config.verify,
            timeout=30,
        )
        response.raise_for_status()
        events = response.json()
        alerts = []
        for event in events:
            alert = self._format_alert(event)
            if isinstance(alert, list):
                alerts.extend(alert)
            else:
                alerts.append(alert)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        check = event.get("check", {})
        entity = event.get("entity", {})
        metadata = check.get("metadata", {})
        entity_metadata = entity.get("metadata", {})

        check_name = metadata.get("name", "unknown")
        entity_name = entity_metadata.get("name", "unknown")
        namespace = metadata.get("namespace", entity_metadata.get("namespace", "default"))

        alert_id = f"{namespace}/{entity_name}/{check_name}"
        status_code = check.get("status", 0)
        output = check.get("output", "")
        issued = check.get("issued", 0)

        severity = SensuProvider.SEVERITIES_MAP.get(status_code, AlertSeverity.HIGH)
        status = SensuProvider.STATUS_MAP.get(status_code, AlertStatus.FIRING)

        last_received = (
            datetime.datetime.fromtimestamp(issued, tz=datetime.timezone.utc).isoformat()
            if issued
            else datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )

        labels = {**metadata.get("labels", {}), **entity_metadata.get("labels", {})}
        annotations = {**metadata.get("annotations", {}), **check.get("metadata", {}).get("annotations", {})}

        alert = AlertDto(
            id=alert_id,
            name=check_name,
            description=output or check_name,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["sensu"],
            service=entity_name,
            environment=namespace,
            labels=labels,
            annotations=annotations,
            payload=event,
        )
        alert.fingerprint = SensuProvider.get_alert_fingerprint(
            alert, fingerprint_fields=["id"]
        )
        return alert

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("Sensu provider does not support notify()")


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "sensu_api_url": os.environ.get("SENSU_API_URL", "http://localhost:8080"),
            "api_key": os.environ.get("SENSU_API_KEY", ""),
            "namespace": os.environ.get("SENSU_NAMESPACE", "default"),
        }
    )
    from keep.contextmanager.contextmanager import ContextManager

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = SensuProvider(context_manager, "sensu-prod", config)
    print(provider.get_alerts())
