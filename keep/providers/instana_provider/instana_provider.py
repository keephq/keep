"""
InstanaProvider is a class that allows to pull events/alerts from Instana
and receive webhook notifications from Instana's alerting engine.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class InstanaProviderAuthConfig:
    """
    InstanaProviderAuthConfig holds the authentication configuration for Instana.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Instana API Token",
            "hint": "Generate at Settings → API Tokens in your Instana dashboard",
            "sensitive": True,
        },
    )
    instana_base_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Instana Base URL",
            "hint": "e.g. https://mycompany.instana.io or your self-hosted endpoint",
            "validation": "any_http_url",
        },
    )


class InstanaProvider(BaseProvider):
    """Pull events and receive webhook alerts from Instana APM."""

    PROVIDER_DISPLAY_NAME = "Instana"
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]
    PROVIDER_TAGS = ["alert", "monitoring", "apm"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_events",
            description="Read events and alerts from Instana.",
            mandatory=True,
            documentation_url="https://instana.github.io/openapi/#operation/getEvents",
        ),
    ]

    # Instana uses numeric severity: 10 = critical, 5 = warning, -1 = info/change
    SEVERITIES_MAP = {
        10: AlertSeverity.CRITICAL,
        5: AlertSeverity.WARNING,
        -1: AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "CLOSED": AlertStatus.RESOLVED,
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = InstanaProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"apiToken {self.authentication_config.api_token}",
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        return str(self.authentication_config.instana_base_url).rstrip("/")

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self._base_url()}/api/infrastructure-monitoring/snapshots",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code in (200, 204):
                return {"read_events": True}
            # Also try events endpoint
            response = requests.get(
                f"{self._base_url()}/api/events",
                headers=self._get_headers(),
                params={"windowSize": 60000},
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_events": True}
            return {
                "read_events": f"HTTP {response.status_code}: {response.text}"
            }
        except Exception as e:
            return {"read_events": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            # Pull events from the last 24 hours
            window_size_ms = 24 * 60 * 60 * 1000  # 24h in milliseconds
            response = requests.get(
                f"{self._base_url()}/api/events",
                headers=self._get_headers(),
                params={"windowSize": window_size_ms},
                timeout=30,
            )
            response.raise_for_status()
            events = response.json()

            for event in events:
                try:
                    alert = self._event_to_alert_dto(event)
                    alerts.append(alert)
                except Exception as e:
                    self.logger.warning(f"Failed to convert event to alert: {e}")

        except Exception as e:
            self.logger.error(f"Failed to get events from Instana: {e}")

        return alerts

    def _event_to_alert_dto(self, event: dict) -> AlertDto:
        event_id = event.get("id", "")
        severity_num = event.get("severity", -1)
        severity = self.SEVERITIES_MAP.get(severity_num, AlertSeverity.INFO)

        state = event.get("state", "OPEN")
        end_ts = event.get("end", -1)
        if end_ts and end_ts > 0:
            status = AlertStatus.RESOLVED
        else:
            status = self.STATUS_MAP.get(state, AlertStatus.FIRING)

        start_ts = event.get("start") or event.get("triggeredAt")
        if start_ts:
            last_received = datetime.datetime.fromtimestamp(
                start_ts / 1000, tz=datetime.timezone.utc
            ).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return AlertDto(
            id=event_id,
            name=event.get("title", event.get("text", "Instana Event")),
            description=event.get("problem", event.get("text", "")),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["instana"],
            fingerprint=event_id,
            entity_label=event.get("entityLabel", ""),
            entity_type=event.get("entityType", ""),
            event_type=event.get("type", ""),
            suggestion=event.get("suggestion", ""),
            incident_id=event.get("incidentId", ""),
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format an Instana webhook/alert payload into an AlertDto.

        Instana sends event objects via alert channels (webhook integration).
        """
        event_id = event.get("id", "")
        severity_num = event.get("severity", -1)
        severity = InstanaProvider.SEVERITIES_MAP.get(severity_num, AlertSeverity.INFO)

        state = event.get("state", "OPEN")
        end_ts = event.get("end", -1)
        if end_ts and end_ts > 0:
            status = AlertStatus.RESOLVED
        else:
            status = InstanaProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        start_ts = event.get("start") or event.get("triggeredAt")
        if start_ts:
            last_received = datetime.datetime.fromtimestamp(
                start_ts / 1000, tz=datetime.timezone.utc
            ).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        alert = AlertDto(
            id=event_id,
            name=event.get("title", event.get("text", "Instana Event")),
            description=event.get("problem", event.get("text", "")),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["instana"],
            fingerprint=event_id,
            entity_label=event.get("entityLabel", ""),
            entity_type=event.get("entityType", ""),
            event_type=event.get("type", ""),
            suggestion=event.get("suggestion", ""),
            incident_id=event.get("incidentId", ""),
        )
        alert.fingerprint = (
            InstanaProvider.get_alert_fingerprint(
                alert, InstanaProvider.FINGERPRINT_FIELDS
            )
            if event_id
            else None
        )
        return alert


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    api_token = os.environ.get("INSTANA_API_TOKEN")
    base_url = os.environ.get("INSTANA_BASE_URL")

    if not api_token or not base_url:
        raise Exception(
            "INSTANA_API_TOKEN and INSTANA_BASE_URL environment variables are required"
        )

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Instana Provider",
        authentication={
            "api_token": api_token,
            "instana_base_url": base_url,
        },
    )
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="instana-keephq",
        provider_type="instana",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    print("Scopes:", scopes)
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
