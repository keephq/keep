"""SolarWinds webhook provider."""

from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class SolarwindsProvider(BaseProvider):
    """Get alerts from SolarWinds into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = "Receive SolarWinds alerts via webhook"
    webhook_template = ""
    webhook_markdown = """
1. In SolarWinds Orion, configure an Alert Action to send a webhook/HTTP POST.
2. Point it to Keep webhook URL: `{keep_webhook_api_url}`.
3. Send JSON payload with fields like `AlertObjectID`, `AlertName`, `Severity`, `NodeName`, `Message`.
4. Optional fields: `TriggeredDateTime`, `IsAcknowledged`, `IsActive`, `AlertDetailsUrl`.
"""

    SEVERITY_MAP = {
        "INFORMATION": AlertSeverity.INFO,
        "INFO": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "MINOR": AlertSeverity.WARNING,
        "MAJOR": AlertSeverity.HIGH,
        "CRITICAL": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """Dispose provider resources."""
        pass

    def validate_config(self) -> None:
        """SolarWinds webhook provider requires no configuration validation."""
        pass

    @staticmethod
    def _get(event: dict, *keys: str):
        for key in keys:
            val = event.get(key)
            if val not in (None, ""):
                return val
        return None

    @staticmethod
    def _to_bool(value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        if isinstance(value, int):
            return value != 0
        return default

    @staticmethod
    def _parse_last_received(event: dict) -> str:
        default = datetime.now(timezone.utc).isoformat()
        raw = SolarwindsProvider._get(
            event,
            "TriggeredDateTime",
            "TriggeredAt",
            "timestamp",
            "time",
            "date",
        )
        if not raw:
            return default
        text = str(raw).strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return default

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        event = event or {}
        severity_raw = str(
            SolarwindsProvider._get(event, "Severity", "AlertSeverity") or "INFO"
        ).strip().upper()
        severity = SolarwindsProvider.SEVERITY_MAP.get(severity_raw, AlertSeverity.INFO)

        is_ack = SolarwindsProvider._to_bool(
            SolarwindsProvider._get(event, "IsAcknowledged", "Acknowledged"),
            default=False,
        )
        # If provider doesn't send IsActive, treat alert as active by default.
        is_active = SolarwindsProvider._to_bool(
            SolarwindsProvider._get(event, "IsActive", "Active", "Triggered"),
            default=True,
        )

        if not is_active:
            status = AlertStatus.RESOLVED
        elif is_ack:
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = AlertStatus.FIRING

        alert_id = SolarwindsProvider._get(
            event,
            "AlertObjectID",
            "AlertID",
            "id",
            "alert_id",
        )
        if not alert_id:
            alert_id = ":".join(
                [
                    str(
                        SolarwindsProvider._get(event, "NodeName", "HostName")
                        or "unknown-host"
                    ),
                    str(SolarwindsProvider._get(event, "AlertName", "Name") or "solarwinds-alert"),
                ]
            )

        node = SolarwindsProvider._get(event, "NodeName", "HostName", "EntityName")
        entity = SolarwindsProvider._get(event, "EntityCaption", "ObjectName")
        name = SolarwindsProvider._get(event, "AlertName", "Name") or "SolarWinds alert"
        if node and entity:
            name = f"{node} - {entity}"

        message = SolarwindsProvider._get(event, "Message", "AlertMessage", "Description")

        return AlertDto(
            id=str(alert_id),
            name=str(name),
            status=status,
            severity=severity,
            host=node,
            service=entity,
            source=["solarwinds"],
            description=message or str(name),
            message=message,
            lastReceived=SolarwindsProvider._parse_last_received(event),
            alert_url=SolarwindsProvider._get(event, "AlertDetailsUrl", "DetailsUrl"),
            labels={"severity": severity_raw},
            pushed=True,
        )
