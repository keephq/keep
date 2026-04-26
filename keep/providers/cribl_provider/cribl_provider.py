"""
Cribl provider for Keep.

Cribl is an observability pipeline platform (Cribl Stream, Cribl Edge, Cribl Search)
that collects, transforms, and routes logs, metrics, and traces from any source to
any destination. Cribl can forward processed events to Keep via an HTTP output
configured as a webhook destination.

This provider supports:
- Push: receives events forwarded from Cribl Stream/Edge HTTP output
- Parses Cribl's generic event envelope as well as common passthrough payloads
  from upstream sources (Splunk HEC, syslog, CloudWatch, etc.)

References:
- https://docs.cribl.io/stream/
- https://docs.cribl.io/stream/destinations-http/
"""

import dataclasses
import datetime
import uuid

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CriblProviderAuthConfig:
    """Authentication configuration for the Cribl webhook provider."""

    webhook_api_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Optional API key to authenticate incoming Cribl webhook events",
            "sensitive": True,
            "hint": "Set this to match the Authorization header token configured in your Cribl HTTP destination",
        },
    )


class CriblProvider(BaseProvider):
    """Receive processed observability events from Cribl Stream/Edge into Keep."""

    PROVIDER_DISPLAY_NAME = "Cribl"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Data Pipeline"]

    webhook_description = (
        "Configure a Cribl HTTP output destination to forward events to Keep."
    )
    webhook_template = ""
    webhook_markdown = """
To forward events from Cribl Stream or Cribl Edge to Keep, add an **HTTP** output
destination in your Cribl pipeline.

### Cribl Stream / Cribl Edge — HTTP Output Setup

1. In Cribl, navigate to **Routing → QuickConnect** (or open your pipeline in **Processing → Pipelines**).
2. Click **+ Add Destination → HTTP**.
3. Set the **URL** to:
   ```
   {keep_webhook_api_url}
   ```
4. Set the **Method** to `POST`.
5. Under **Headers**, add:
   - `Content-Type`: `application/json`
   - `x-api-key`: `{api_key}`
6. Under **Format**, select **JSON** (one event per request or a JSON array).
7. Save and deploy the configuration.

### Recommended pipeline enrichment

Before routing to Keep, add a **Serialize** or **Eval** function in your pipeline
to ensure the event contains at minimum:

| Field | Description |
|-------|-------------|
| `_time` | Unix epoch timestamp |
| `host` | Source host |
| `source` or `sourcetype` | Data origin |
| `severity` | Alert severity level |
| `message` or `_raw` | Event message |
| `status` | Alert status (`firing` / `resolved`) |

Cribl's own **Notifications** feature (Cribl.Cloud / Cribl Stream 4.x) also
supports webhook notifications — point those directly at the Keep webhook URL.
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CriblProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _parse_timestamp(event: dict) -> str:
        """Extract and normalise the event timestamp."""
        # Cribl preserves the original _time as a Unix epoch float
        raw_time = event.get("_time") or event.get("time") or event.get("timestamp")
        if raw_time is not None:
            try:
                ts = float(raw_time)
                return datetime.datetime.fromtimestamp(
                    ts, tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse a Cribl HTTP output event into an AlertDto.

        Cribl forwards events in the original format of the upstream source,
        optionally enriched with Cribl-specific metadata fields. This method
        handles both Cribl-native and passthrough payloads.

        Common event shapes accepted:
        - Generic JSON with severity/status/message fields
        - Splunk HEC events (sourcetype, host, event)
        - CloudWatch Logs events (logGroup, logStream, message)
        - Syslog-structured events (facility, priority, msg)
        - Cribl.Cloud notification payloads (type, condition, value)
        """
        # Handle Cribl.Cloud / Cribl Stream notification format
        if "condition" in event and "type" in event:
            return CriblProvider._format_cribl_notification(event)

        # Handle array payloads (Cribl batch mode)
        if isinstance(event, list):
            return [
                CriblProvider._format_alert(e, provider_instance)
                for e in event
                if isinstance(e, dict)
            ]

        # --- Extract common fields with fallback chains ---
        # ID
        alert_id = (
            event.get("id")
            or event.get("_id")
            or event.get("event_id")
            or str(uuid.uuid4())
        )

        # Name / alert name
        name = (
            event.get("name")
            or event.get("alert_name")
            or event.get("sourcetype")
            or event.get("source")
            or event.get("logGroup")
            or "cribl-event"
        )

        # Description / message
        description = (
            event.get("message")
            or event.get("msg")
            or event.get("_raw")
            or event.get("event")
            or event.get("description")
            or ""
        )
        if isinstance(description, dict):
            description = str(description)

        # Host / service
        hostname = event.get("host") or event.get("hostname") or ""
        service = (
            event.get("service")
            or event.get("source")
            or event.get("sourcetype")
            or None
        )

        # Severity
        raw_severity = (
            event.get("severity")
            or event.get("level")
            or event.get("priority")
            or event.get("log_level")
            or ""
        )
        severity = CriblProvider.SEVERITIES_MAP.get(
            str(raw_severity).lower(), AlertSeverity.INFO
        )

        # Status
        raw_status = event.get("status") or event.get("state") or ""
        status = CriblProvider.STATUS_MAP.get(
            str(raw_status).lower(), AlertStatus.FIRING
        )

        # Fingerprint — stable across re-deliveries
        fp_string = f"cribl-{name}-{hostname}"
        fingerprint = str(uuid.uuid5(uuid.NAMESPACE_DNS, fp_string))

        return AlertDto(
            id=alert_id,
            fingerprint=fingerprint,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=["cribl"],
            lastReceived=CriblProvider._parse_timestamp(event),
            hostname=hostname,
            service=service,
            environment=event.get("environment") or event.get("env") or "unknown",
            payload=event,
        )

    @staticmethod
    def _format_cribl_notification(event: dict) -> AlertDto:
        """
        Parse a Cribl.Cloud / Cribl Stream 4.x platform notification.
        These are triggered by Cribl's internal notification rules (e.g.,
        backpressure, worker unhealthy, search job completed).
        """
        condition = event.get("condition", "")
        notif_type = event.get("type", "alert")
        value = event.get("value", "")
        description = event.get("description") or f"{notif_type}: {condition} = {value}"
        name = condition or notif_type or "cribl-notification"
        fingerprint = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cribl-notif-{name}"))

        return AlertDto(
            id=event.get("id", str(uuid.uuid4())),
            fingerprint=fingerprint,
            name=name,
            description=description,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            source=["cribl"],
            lastReceived=CriblProvider._parse_timestamp(event),
            payload=event,
        )

    def dispose(self):
        pass
