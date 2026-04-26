"""
SignozProvider is a class that provides a way to interact with SigNoz observability alerts.
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
class SignozProviderAuthConfig:
    """
    SigNoz authentication configuration.
    """

    signoz_api_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SigNoz API URL",
            "hint": "http://signoz-backend:8080",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SigNoz API key (SIGNOZ-API-KEY header)",
            "hint": "Generate from SigNoz Settings > API Keys",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class SignozProvider(BaseProvider):
    """Get alerts from SigNoz into Keep."""

    PROVIDER_DISPLAY_NAME = "SigNoz"
    PROVIDER_CATEGORY = ["Monitoring", "Observability"]
    PROVIDER_TAGS = ["alert"]

    webhook_description = "SigNoz supports alert notification channels. Configure Keep as a webhook channel to receive alerts."
    webhook_template = ""
    webhook_markdown = """
1. In SigNoz, navigate to **Settings > Alert Channels**.
2. Click **New Channel** and select **Webhook**.
3. Set the **Webhook URL** to `{keep_webhook_api_url}`.
4. Add a header `x-api-key` with value `{api_key}`.
5. Save the channel and attach it to your alert rules.
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read triggered alerts from SigNoz API",
            mandatory=True,
            documentation_url="https://signoz.io/docs/operate/api-documentation/",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "p1": AlertSeverity.CRITICAL,
        "p2": AlertSeverity.HIGH,
        "p3": AlertSeverity.WARNING,
        "p4": AlertSeverity.LOW,
        "p5": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "no_data": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for SigNoz provider.
        """
        self.authentication_config = SignozProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {"alerts:read": False}
        try:
            url = f"{self.authentication_config.signoz_api_url}/api/v1/rules"
            response = requests.get(
                url,
                headers={"SIGNOZ-API-KEY": self.authentication_config.api_key},
                verify=self.authentication_config.verify,
                timeout=10,
            )
            if response.status_code == 200:
                scopes["alerts:read"] = True
            else:
                scopes["alerts:read"] = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as e:
            scopes["alerts:read"] = str(e)
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active alerts from SigNoz /api/v1/rules (alert rules with state)."""
        url = f"{self.authentication_config.signoz_api_url}/api/v1/rules"
        response = requests.get(
            url,
            headers={"SIGNOZ-API-KEY": self.authentication_config.api_key},
            verify=self.authentication_config.verify,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        rules = data.get("data", data) if isinstance(data, dict) else data

        alerts = []
        for rule in rules:
            for alert in rule.get("alerts", []):
                alert["_rule_name"] = rule.get("name", "")
                alert["_rule_id"] = str(rule.get("id", ""))
                dto = self._format_alert(alert)
                if isinstance(dto, list):
                    alerts.extend(dto)
                else:
                    alerts.append(dto)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        labels = event.get("labels", {})
        annotations = event.get("annotations", {})

        rule_name = event.get("_rule_name") or labels.get("alertname", "unknown")
        rule_id = event.get("_rule_id", "")
        state = event.get("state", "firing").lower()
        severity_raw = (labels.get("severity") or labels.get("priority") or "info").lower()

        alert_id = f"{rule_id}/{labels.get('alertname', rule_name)}"
        description = annotations.get("description") or annotations.get("summary") or rule_name

        status = SignozProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        severity = SignozProvider.SEVERITIES_MAP.get(severity_raw, AlertSeverity.INFO)

        active_at_raw = event.get("activeAt")
        if active_at_raw:
            try:
                last_received = datetime.datetime.fromisoformat(
                    active_at_raw.replace("Z", "+00:00")
                ).isoformat()
            except ValueError:
                last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        alert = AlertDto(
            id=alert_id,
            name=rule_name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["signoz"],
            labels=labels,
            annotations=annotations,
            payload=event,
        )
        alert.fingerprint = SignozProvider.get_alert_fingerprint(
            alert, fingerprint_fields=["id"]
        )
        return alert

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("SigNoz provider does not support notify()")


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "signoz_api_url": os.environ.get("SIGNOZ_API_URL", "http://localhost:8080"),
            "api_key": os.environ.get("SIGNOZ_API_KEY", ""),
        }
    )
    from keep.contextmanager.contextmanager import ContextManager

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = SignozProvider(context_manager, "signoz-prod", config)
    print(provider.get_alerts())
