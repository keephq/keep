"""
Mezmo provider for Keep.

Mezmo (formerly LogDNA) sends webhook alerts when log-based alert conditions
are met via their Views/Alerts system. Keep receives these as JSON POST
requests to its webhook endpoint.

No external libraries required — this provider only parses JSON payloads.
"""

import logging
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class MezmoProvider(BaseProvider):
    """Receive Mezmo (LogDNA) log-based alert webhooks."""

    PROVIDER_DISPLAY_NAME = "Mezmo"
    PROVIDER_CATEGORY = ["Monitoring", "Logs"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = []
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_markdown = """
1. In the [Mezmo UI](https://app.mezmo.com), open your **Organization Settings**.
2. Go to **Alerts → Webhook**.
3. Add a new webhook destination with the URL `{keep_webhook_api_url}`.
4. Add the HTTP header `X-API-KEY` with your Keep API key.
5. Attach this webhook destination to one or more **Views → Alerts** that you want forwarded to Keep.
"""

    # Mezmo alert level strings → Keep severity
    _SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
        "trace": AlertSeverity.LOW,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No authentication required — webhook-only provider."""
        pass

    def dispose(self):
        """Nothing to clean up."""
        pass

    @staticmethod
    def _resolve_severity(event: dict) -> AlertSeverity:
        """Map Mezmo alert level to Keep severity."""
        level = (
            event.get("level")
            or event.get("severity")
            or event.get("log_level")
            or ""
        ).lower()
        return MezmoProvider._SEVERITY_MAP.get(level, AlertSeverity.INFO)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> "AlertDto | list[AlertDto]":
        """
        Parse a Mezmo webhook alert payload into an AlertDto.

        Mezmo webhook fields (varies by alert type — presence is best-effort):
          - alert_id (str): Unique alert ID
          - name / title (str): Name of the view or alert rule
          - description (str): Alert description or matched log line summary
          - level / severity / log_level (str): Log level that triggered
          - timestamp (str|int): When the alert fired (ISO-8601 or epoch ms)
          - query (str): The log search query that triggered
          - url (str): Deep-link to the Mezmo view
          - lines (list[dict]): Matched log lines (each has timestamp, app, line, level)
          - app (str): Application name
          - host (str): Host that generated the matching logs
          - account (str): Mezmo account / organization
          - webhook_id / id (str): Webhook or alert identifier
        """
        alert_id = event.get("alert_id") or event.get("webhook_id") or event.get("id")
        name = event.get("name") or event.get("title") or "Mezmo Alert"

        # Build a useful description from available fields
        description = event.get("description") or ""
        if not description:
            lines = event.get("lines", [])
            if lines and isinstance(lines, list):
                # Use the first matched log line as description
                first = lines[0] if isinstance(lines[0], dict) else {}
                description = first.get("line") or first.get("message") or name
            else:
                description = name

        severity = MezmoProvider._resolve_severity(event)

        # Mezmo alerts don't carry explicit open/close status — treat as FIRING
        # unless the payload explicitly says otherwise
        status_raw = (event.get("status") or "").upper()
        status = AlertStatus.RESOLVED if status_raw == "RESOLVED" else AlertStatus.FIRING

        # Timestamp handling: ISO string or epoch-ms integer
        raw_ts = event.get("timestamp")
        last_received: Optional[str] = None
        if isinstance(raw_ts, (int, float)):
            from datetime import datetime, timezone
            ts_sec = raw_ts / 1000 if raw_ts > 1e10 else raw_ts
            last_received = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat()
        elif isinstance(raw_ts, str) and raw_ts:
            last_received = raw_ts

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=["mezmo"],
            host=event.get("host"),
            app=event.get("app"),
            query=event.get("query"),
            url=event.get("url"),
            account=event.get("account"),
            lastReceived=last_received,
        )

        return alert


if __name__ == "__main__":
    pass
