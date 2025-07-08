import logging
from typing import Any

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

class NagiosProvider(BaseProvider):
    """Core Class for Nagios Provider.
    Handles all Webhook logic"""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alerting", "monitoring"]
    PROVIDER_CATEGORY = "monitoring"

    _state_mapping = {
        "OK": AlertSeverity.LOW,
        "WARNING": AlertSeverity.WARNING,
        "UNKNOWN": AlertSeverity.INFO,
        "CRITICAL": AlertSeverity.HIGH,
        "UP": AlertSeverity.LOW,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL
    }

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
    
    def _format_alert(self, event: dict) -> AlertDto:
        severity = AlertSeverity.INFO
        if "service_state" in event:
            severity = self._state_mapping.get(event.get("service_state", AlertSeverity.INFO))
        elif "host_state" in event:
            severity = self._state_mapping.get(event.get("host_state"), AlertSeverity.INFO)

        status = AlertStatus.FIRING if severity != AlertSeverity.LOW else AlertSeverity.RESOLVED

        return AlertDto(
            id=event.get("id"), #nagios doesnt have unique event id. so generate fingerprint ...
            name=event.get("service_description") or event.get("host_name"),
            status=status,
            severity=severity,
            lastReceived=event.get("timestamp"),
            description=event.get("output"),
            source=["nagios"],
            host=event.get("host_name"),
            service=event.get("service_description"),
            **event
        )
