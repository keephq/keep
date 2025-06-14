"""Falco provider to ingest Falco security alerts."""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class FalcoProvider(BaseProvider):
    """Get alerts from Falco into Keep."""

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Security"]
    FINGERPRINT_FIELDS = ["rule"]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No configuration required for Falco provider."""
        pass

    SEVERITIES_MAP = {
        "emergency": AlertSeverity.CRITICAL,
        "alert": AlertSeverity.CRITICAL,
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "notice": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
    }

    @staticmethod
    def _format_alert(event: dict, provider_instance: BaseProvider | None = None) -> AlertDto:
        rule = event.get("rule", "")
        description = event.get("output", "")
        severity = FalcoProvider.SEVERITIES_MAP.get(event.get("priority", "").lower(), AlertSeverity.INFO)
        last_received = event.get("time")
        environment = event.get("hostname", "unknown")

        alert = AlertDto(
            name=rule,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            environment=environment,
            source=["falco"],
        )
        alert.fingerprint = FalcoProvider.get_alert_fingerprint(
            alert, fingerprint_fields=FalcoProvider.FINGERPRINT_FIELDS
        )
        return alert
