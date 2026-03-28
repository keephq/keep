"""
Kapacitor provider for Keep.

Kapacitor is InfluxData's data processing engine for InfluxDB time-series data.
It evaluates TICKscripts (alert rules) and fires alerts through handler chains
that include an HTTP POST handler — which is how Keep integrates with it.

Integration modes:
  1. Webhook (Push) — Kapacitor's HTTP POST handler sends alert payloads to
     Keep's webhook endpoint.  Configure via a Kapacitor handler file or by
     adding a POST handler in your TICKscript.
  2. Pull — queries the Kapacitor REST API for the status of all tasks
     (enabled/disabled) and retrieves stored alert topics + events.

References:
  https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/post/
  https://docs.influxdata.com/kapacitor/v1/working/api/
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


@pydantic.dataclasses.dataclass
class KapacitorProviderAuthConfig:
    """Authentication configuration for Kapacitor."""

    kapacitor_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kapacitor server URL",
            "hint": "e.g. http://kapacitor:9092",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kapacitor username (if authentication is enabled)",
            "sensitive": False,
        },
        default=None,
    )
    password: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kapacitor password (if authentication is enabled)",
            "sensitive": True,
        },
        default=None,
    )


class KapacitorProvider(BaseProvider):
    """Receive Kapacitor alert notifications via webhook and pull task/alert status."""

    webhook_description = (
        "Configure a Kapacitor HTTP POST handler to forward alert events to Keep."
    )
    webhook_template = ""
    webhook_markdown = """
To send Kapacitor alerts to Keep via its HTTP POST event handler:

**Option 1 — Handler file** (recommended):

Create a handler file `/etc/kapacitor/handlers/keep.yaml`:
```yaml
id: keep-handler
kind: post
options:
  url: {keep_webhook_api_url}
  headers:
    x-api-key: {api_key}
  skipSSLVerification: false
```
Register it with `kapacitor define-handler keep.yaml`.

**Option 2 — TICKscript**:

Inside your TICKscript alert node, add:
```
|alert()
  .post('{keep_webhook_api_url}')
  .header('x-api-key', '{api_key}')
```

Kapacitor will POST an alert payload to Keep whenever the alert fires or recovers.
"""

    PROVIDER_DISPLAY_NAME = "Kapacitor"
    PROVIDER_TAGS = ["alert", "monitoring", "time-series"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_ICON = "https://www.influxdata.com/favicon.ico"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Can reach the Kapacitor REST API",
            mandatory=True,
            alias="Connectivity",
        )
    ]

    FINGERPRINT_FIELDS = ["id"]

    # Kapacitor uses string levels in alert payloads
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
        "OK": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "CRITICAL": AlertStatus.FIRING,
        "ERROR": AlertStatus.FIRING,
        "WARNING": AlertStatus.FIRING,
        "INFO": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = KapacitorProviderAuthConfig(
            **self.config.authentication
        )

    def _base_url(self) -> str:
        return str(self.authentication_config.kapacitor_url).rstrip("/")

    def _get_session(self) -> requests.Session:
        session = requests.Session()
        username = self.authentication_config.username
        password = self.authentication_config.password
        if username and password:
            session.auth = (username, password)
        return session

    def validate_scopes(self) -> dict[str, bool | str]:
        """Check connectivity to the Kapacitor REST API."""
        try:
            session = self._get_session()
            resp = session.get(
                f"{self._base_url()}/kapacitor/v1/ping",
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return {"connectivity": True}
            return {
                "connectivity": f"HTTP {resp.status_code}: {resp.text[:200]}"
            }
        except Exception as e:
            return {"connectivity": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alert events from Kapacitor's alert topics endpoint.

        The /kapacitor/v1/alerts/topics endpoint returns a list of active alert
        topics.  For each topic we fetch the current events.
        """
        try:
            session = self._get_session()
            topics_resp = session.get(
                f"{self._base_url()}/kapacitor/v1/alerts/topics",
                timeout=15,
            )
            topics_resp.raise_for_status()
            topics = topics_resp.json().get("topics", [])
        except Exception as e:
            self.logger.error(f"Kapacitor: failed to fetch topics: {e}")
            return []

        alerts: list[AlertDto] = []
        for topic in topics:
            topic_id = topic.get("id", "")
            try:
                events_resp = session.get(
                    f"{self._base_url()}/kapacitor/v1/alerts/topics/{topic_id}/events",
                    timeout=15,
                )
                events_resp.raise_for_status()
                events = events_resp.json().get("events", [])
                for event in events:
                    dto = self._format_event(event, topic_id)
                    if dto:
                        alerts.append(dto)
            except Exception as e:
                self.logger.warning(
                    f"Kapacitor: failed to fetch events for topic '{topic_id}': {e}"
                )
        return alerts

    def _format_event(self, event: dict, topic_id: str) -> "AlertDto | None":
        """Convert a Kapacitor alert event (pull mode) to an AlertDto."""
        state = event.get("state", {})
        level = state.get("level", "INFO")
        message = state.get("message", "")
        timestamp_str = state.get("timestamp", "")
        event_id = event.get("id", "")

        severity = self.SEVERITIES_MAP.get(level, AlertSeverity.HIGH)
        status = self.STATUS_MAP.get(level, AlertStatus.FIRING)

        last_received = None
        if timestamp_str:
            try:
                # Kapacitor timestamps are RFC3339 e.g. "2026-03-29T12:00:00Z"
                last_received = timestamp_str
            except Exception:
                pass

        return AlertDto(
            id=event_id or topic_id,
            name=event_id or topic_id,
            description=message,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["kapacitor"],
            labels={
                "topic": topic_id,
                "level": level,
            },
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Kapacitor HTTP POST alert payload into an AlertDto.

        Kapacitor's POST handler sends a JSON payload structured as:
        {
          "id":           "cpu_alert:host=web01",
          "message":      "CPU is HIGH on web01: cpu_usage=92.0",
          "details":      "<html>...",
          "time":         "2026-03-29T12:34:56.789Z",
          "duration":     60000000000,
          "level":        "CRITICAL",
          "data": {
            "series": [
              {
                "name":    "cpu",
                "tags":    {"host": "web01"},
                "columns": ["time","cpu_usage_idle"],
                "values":  [["2026-03-29T12:34:56Z", 8.0]]
              }
            ]
          },
          "previousLevel": "OK",
          "recoverable":   true
        }
        """
        level = event.get("level", "INFO")
        message = event.get("message", "")
        alert_id = event.get("id", "")
        time_str = event.get("time", "")
        details = event.get("details", "")
        previous_level = event.get("previousLevel", "")

        severity = KapacitorProvider.SEVERITIES_MAP.get(level, AlertSeverity.HIGH)
        status = KapacitorProvider.STATUS_MAP.get(level, AlertStatus.FIRING)

        # Build labels from series tags
        labels: dict = {"level": level}
        if previous_level:
            labels["previousLevel"] = previous_level
        data = event.get("data", {})
        series = data.get("series", [])
        if series:
            tags = series[0].get("tags", {})
            labels.update(tags)
            labels["measurement"] = series[0].get("name", "")

        return AlertDto(
            id=alert_id,
            name=alert_id or message[:80],
            description=message,
            severity=severity,
            status=status,
            lastReceived=time_str or None,
            source=["kapacitor"],
            labels=labels,
        )
