"""
KapacitorProvider receives alerts from InfluxData Kapacitor
and can query alert topics via the Kapacitor HTTP API.
"""

import dataclasses
import logging
from datetime import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)

KAPACITOR_SEVERITY_MAP = {
    "CRITICAL": AlertSeverity.CRITICAL,
    "WARNING": AlertSeverity.WARNING,
    "INFO": AlertSeverity.INFO,
    "OK": AlertSeverity.LOW,
}

KAPACITOR_STATUS_MAP = {
    "CRITICAL": AlertStatus.FIRING,
    "WARNING": AlertStatus.FIRING,
    "INFO": AlertStatus.FIRING,
    "OK": AlertStatus.RESOLVED,
}


@pydantic.dataclasses.dataclass
class KapacitorProviderAuthConfig:
    """Kapacitor authentication configuration."""

    url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kapacitor base URL (e.g. http://localhost:9092)",
            "sensitive": False,
            "hint": "http://localhost:9092",
        }
    )
    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kapacitor username (optional)",
            "sensitive": False,
        },
        default=None,
    )
    password: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kapacitor password (optional)",
            "sensitive": True,
        },
        default=None,
    )


class KapacitorProvider(BaseProvider):
    """Receive and query alerts from InfluxData Kapacitor."""

    PROVIDER_DISPLAY_NAME = "Kapacitor"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts_read",
            description="Read alert topics from Kapacitor",
            mandatory=True,
            alias="Alerts Read",
        ),
    ]

    webhook_description = "Receive Kapacitor alert notifications"
    webhook_markdown = """
To send Kapacitor alerts to Keep:

1. In your TICKscript, add an HTTP POST alert handler:
   ```
   |alert()
       .post('{keep_webhook_api_url}')
       .header('X-API-KEY', '{api_key}')
   ```
2. Alerts will be sent to Keep automatically when triggered.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = KapacitorProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        scopes = {}
        try:
            response = requests.get(
                f"{self.authentication_config.url.rstrip('/')}/kapacitor/v1/alerts/topics",
                auth=self._get_auth(),
                timeout=10,
            )
            response.raise_for_status()
            scopes["alerts_read"] = True
        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            scopes["alerts_read"] = str(e)
        return scopes

    def _get_auth(self):
        if self.authentication_config.username:
            return (
                self.authentication_config.username,
                self.authentication_config.password or "",
            )
        return None

    def _query(self, **kwargs) -> list[AlertDto]:
        """Query Kapacitor alert topics."""
        base_url = self.authentication_config.url.rstrip("/")
        url = f"{base_url}/kapacitor/v1/alerts/topics"

        response = requests.get(url, auth=self._get_auth(), timeout=30)
        response.raise_for_status()

        topics = response.json().get("topics", [])
        alerts = []

        for topic in topics:
            topic_id = topic.get("id", "")
            level = topic.get("level", "OK").upper()

            # Fetch events for each topic
            events_url = f"{base_url}/kapacitor/v1/alerts/topics/{topic_id}/events"
            try:
                events_response = requests.get(
                    events_url, auth=self._get_auth(), timeout=30
                )
                events_response.raise_for_status()
                events = events_response.json().get("events", [])
            except Exception:
                events = []

            for event in events:
                alert = self._format_alert(event, provider_instance=self)
                if isinstance(alert, list):
                    alerts.extend(alert)
                else:
                    alerts.append(alert)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse a Kapacitor alert event into an AlertDto.

        Kapacitor alert JSON format:
        {
            "id": "alert-id",
            "message": "alert message",
            "details": "detailed description",
            "level": "CRITICAL|WARNING|INFO|OK",
            "time": "2024-01-15T10:30:00Z",
            "duration": "5m0s",
            "data": { "series": [...] }
        }
        """
        alert_id = event.get("id", "")
        message = event.get("message", "")
        details = event.get("details", "")
        level = event.get("level", "INFO").upper()
        alert_time = event.get("time", "")
        duration = event.get("duration", "")
        data = event.get("data", {})
        previous_level = event.get("previousLevel", "")

        severity = KAPACITOR_SEVERITY_MAP.get(level, AlertSeverity.INFO)
        status = KAPACITOR_STATUS_MAP.get(level, AlertStatus.FIRING)

        try:
            timestamp = datetime.fromisoformat(
                alert_time.replace("Z", "+00:00")
            ) if alert_time else datetime.utcnow()
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()

        alert = AlertDto(
            id=alert_id,
            name=message or alert_id,
            title=message or alert_id,
            description=details or message,
            severity=severity,
            status=status,
            source=["kapacitor"],
            lastReceived=timestamp.isoformat(),
            startedAt=timestamp.isoformat(),
            duration=duration,
            level=level,
            previous_level=previous_level,
            kapacitor_data=data,
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    config = {
        "authentication": {
            "url": os.environ.get("KAPACITOR_URL", "http://localhost:9092"),
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="kapacitor_test",
        provider_type="kapacitor",
        provider_config=config,
    )
    print("Provider created successfully")
