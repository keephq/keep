"""
FalcoProvider is a class that allows you to receive alerts from Falco runtime security engine.
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
class FalcoProviderAuthConfig:
    """
    Falco authentication configuration.

    Falco Sidekick exposes an HTTP API that Keep can scrape.
    See: https://github.com/falcosecurity/falcosidekick
    """

    falcosidekick_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Falco Sidekick base URL",
            "hint": "http://falcosidekick:2801",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Basic-auth username (if Sidekick is protected)",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Basic-auth password (if Sidekick is protected)",
            "sensitive": True,
        },
        default="",
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class FalcoProvider(BaseProvider):
    """Pull runtime-security alerts from Falco (via Falco Sidekick) into Keep."""

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_CATEGORY = ["Security", "Monitoring"]
    PROVIDER_TAGS = ["alert"]

    # Falco priority → Keep severity
    # https://falco.org/docs/rules/basic-elements/#priority
    SEVERITIES_MAP = {
        "emergency": AlertSeverity.CRITICAL,
        "alert": AlertSeverity.CRITICAL,
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "notice": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="sidekick:read",
            description="Read Falco alerts from the Sidekick /events endpoint",
            mandatory=True,
            documentation_url="https://github.com/falcosecurity/falcosidekick",
        ),
    ]

    webhook_description = (
        "Configure Falco Sidekick to forward events to Keep using its built-in webhook output. "
        "Add the following to your Sidekick configuration:"
    )
    webhook_template = """webhook:
  address: {keep_webhook_api_url}
  customHeaders:
    Authorization: Bearer {api_key}"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate the Falco provider configuration."""
        self.authentication_config = FalcoProviderAuthConfig(
            **self.config.authentication
        )

    def _auth(self):
        username = self.authentication_config.username
        password = self.authentication_config.password
        if username and password:
            return (username, password)
        return None

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {"sidekick:read": False}
        try:
            url = f"{self.authentication_config.falcosidekick_url}/healthz"
            response = requests.get(
                url,
                auth=self._auth(),
                verify=self.authentication_config.verify_ssl,
                timeout=10,
            )
            if response.status_code == 200:
                scopes["sidekick:read"] = True
            else:
                scopes["sidekick:read"] = (
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
        except Exception as e:
            scopes["sidekick:read"] = str(e)
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """Pull recent events from Falco Sidekick /events endpoint."""
        url = f"{self.authentication_config.falcosidekick_url}/events"
        response = requests.get(
            url,
            auth=self._auth(),
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Sidekick /events returns a list of event objects
        if isinstance(data, dict):
            events = data.get("events", data.get("data", []))
        elif isinstance(data, list):
            events = data
        else:
            events = []

        alerts = []
        for event in events:
            alert = self._format_alert(event)
            alerts.append(alert)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Convert a Falco Sidekick event dict into an AlertDto."""
        rule = event.get("rule", "unknown")
        priority = (event.get("priority") or "").lower()
        output = event.get("output", "")
        time_str = event.get("time", "")
        hostname = event.get("hostname", "")
        source = event.get("source", "falco")
        tags = event.get("tags", [])
        output_fields = event.get("output_fields", {}) or {}

        severity = FalcoProvider.SEVERITIES_MAP.get(priority, AlertSeverity.INFO)

        try:
            last_received = (
                datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                .isoformat()
            )
        except (ValueError, AttributeError):
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        labels = {
            "priority": priority,
            "source": source,
            "hostname": hostname,
        }
        if isinstance(tags, list):
            labels["tags"] = ",".join(tags)
        # Merge selected output fields as labels
        for field in ("container.id", "container.name", "proc.name", "k8s.pod.name", "k8s.ns.name"):
            if field in output_fields:
                labels[field.replace(".", "_")] = str(output_fields[field])

        alert_id = output_fields.get("uuid") or output_fields.get("evt.num") or rule

        alert = AlertDto(
            id=str(alert_id),
            name=rule,
            description=output,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["falco"],
            service=hostname,
            labels=labels,
            payload=event,
        )
        alert.fingerprint = FalcoProvider.get_alert_fingerprint(
            alert, fingerprint_fields=["name", "service"]
        )
        return alert

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("Falco provider does not support notify()")


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "falcosidekick_url": os.environ.get(
                "FALCOSIDEKICK_URL", "http://localhost:2801"
            ),
        }
    )
    from keep.contextmanager.contextmanager import ContextManager

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = FalcoProvider(context_manager, "falco-prod", config)
    print(provider.get_alerts())
