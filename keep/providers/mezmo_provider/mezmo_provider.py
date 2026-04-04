"""
MezmoProvider is a provider that integrates Keep with Mezmo (formerly LogDNA)
for log observability and alerting.
"""

import dataclasses
import logging
from datetime import datetime, timezone

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MezmoProviderAuthConfig:
    """
    Mezmo (LogDNA) provider authentication configuration.
    Reference: https://docs.mezmo.com/log-analysis-api
    """

    service_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mezmo Service Key (found in Settings > Organization > API Keys)",
            "hint": "Your Mezmo service key for API authentication",
            "sensitive": True,
        }
    )
    ingestion_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Mezmo Ingestion Key (required for sending logs/events to Mezmo)",
            "sensitive": True,
        },
    )
    hostname: str = dataclasses.field(
        default="api.mezmo.com",
        metadata={
            "required": False,
            "description": "Mezmo API hostname (default: api.mezmo.com)",
            "hint": "Change only if using a private/enterprise Mezmo deployment",
        },
    )


class MezmoProvider(BaseProvider):
    """Get alerts and log-based events from Mezmo (formerly LogDNA) into Keep."""

    PROVIDER_DISPLAY_NAME = "Mezmo"
    PROVIDER_CATEGORY = ["Monitoring", "Logging"]
    PROVIDER_TAGS = ["alert", "logs"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Required to read alerts from Mezmo",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://docs.mezmo.com/log-analysis-api#tag/Alerts",
            alias="Service Key",
        ),
        ProviderScope(
            name="webhook:receive",
            description="Required to receive webhook alert notifications from Mezmo",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://docs.mezmo.com/log-analysis-api#tag/Alerts",
            alias="Webhook Endpoint",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "firing": AlertStatus.FIRING,
        "triggered": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for Mezmo provider."""
        self.authentication_config = MezmoProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Nothing to dispose."""
        pass

    @property
    def __headers(self):
        return {
            "servicekey": self.authentication_config.service_key,
            "Content-Type": "application/json",
        }

    @property
    def __base_url(self):
        return f"https://{self.authentication_config.hostname}"

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            response = requests.get(
                f"{self.__base_url}/v1/config/alert",
                headers=self.__headers,
                timeout=10,
            )
            if response.ok:
                scopes["alerts:read"] = True
            else:
                scopes["alerts:read"] = f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            scopes["alerts:read"] = str(e)

        # Webhook scope is external — assume valid
        scopes["webhook:receive"] = True
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """
        Fetches all alert configurations from Mezmo.
        Note: Mezmo's API returns alert *definitions* (configurations), not historical fired events.
        """
        try:
            response = requests.get(
                f"{self.__base_url}/v1/config/alert",
                headers=self.__headers,
                timeout=15,
            )
            response.raise_for_status()
            alerts_data = response.json()

            # API returns a list of alert configurations
            results = []
            if isinstance(alerts_data, list):
                for alert in alerts_data:
                    results.append(self._format_alert(alert))
            elif isinstance(alerts_data, dict) and "alerts" in alerts_data:
                for alert in alerts_data["alerts"]:
                    results.append(self._format_alert(alert))

            return results
        except Exception:
            self.logger.exception("Failed to get alerts from Mezmo")
            return []

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MezmoProvider" = None
    ) -> AlertDto:
        """
        Format a Mezmo alert payload (webhook or API response) into Keep AlertDto.
        Reference: https://docs.mezmo.com/log-analysis-api#tag/Alerts
        """
        logger = logging.getLogger(__name__)
        logger.info("Formatting Mezmo alert")

        # Webhook payload fields
        name = (
            event.get("name")
            or event.get("alertName")
            or event.get("alert_name")
            or "Mezmo Alert"
        )

        raw_severity = (
            event.get("severity")
            or event.get("level")
            or "info"
        )
        severity = MezmoProvider.SEVERITIES_MAP.get(
            str(raw_severity).lower(), AlertSeverity.INFO
        )

        raw_status = (
            event.get("status")
            or event.get("state")
            or "active"
        )
        status = MezmoProvider.STATUS_MAP.get(
            str(raw_status).lower(), AlertStatus.FIRING
        )

        # Timestamps — Mezmo uses epoch ms or ISO strings
        triggered_at = event.get("triggered_at") or event.get("triggeredAt")
        last_received = None
        if triggered_at:
            try:
                if isinstance(triggered_at, (int, float)):
                    last_received = datetime.fromtimestamp(
                        triggered_at / 1000, tz=timezone.utc
                    ).isoformat()
                else:
                    last_received = triggered_at
            except Exception:
                last_received = str(triggered_at)

        description = (
            event.get("body")
            or event.get("message")
            or event.get("description")
            or event.get("query")
            or ""
        )

        url = event.get("url") or event.get("self") or event.get("viewUrl") or ""

        return AlertDto(
            id=str(event.get("id", event.get("alertid", name))),
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=last_received,
            source=["mezmo"],
            url=url,
            channels=event.get("channels"),
            query=event.get("query"),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="keeptest",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "service_key": os.environ.get("MEZMO_SERVICE_KEY"),
        }
    )
    provider = MezmoProvider(context_manager, "mezmo-test", config)
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alert configs")
    for a in alerts:
        print(a)
