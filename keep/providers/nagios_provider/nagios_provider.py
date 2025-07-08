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
    
    def _determine_severity(self, event: dict) -> AlertSeverity:
        if "service_state" in event:
            return self._state_mapping.get(event.get("service_state"), AlertSeverity.INFO)
        elif "host_state" in event:
            return self._state_mapping.get(event.get("host_state"), AlertSeverity.INFO)
        return AlertSeverity.INFO

    def _format_alert(self, event: dict) -> AlertDto:
        try:
            host_name = event.get("host_name")
            service_description = event.get("service_description")
            
            if not host_name:
                raise ValueError("Missing required field: host_name")
                
            severity = self._determine_severity(event)
            status = AlertStatus.FIRING if severity != AlertSeverity.LOW else AlertStatus.RESOLVED
            
            alert_id = event.get("id")  # nagios doesnt have unique event id. so generate fingerprint ...
            timestamp = event.get("timestamp")
            description = event.get("output")
            
            return AlertDto(
                id=alert_id,
                name=service_description or host_name,
                status=status,
                severity=severity,
                lastReceived=timestamp,
                description=description,
                source=["nagios"],
                host=host_name,
                service=service_description,
                **event
            )
            
        except Exception as e:
            logger.error(f"Error formatting Nagios alert: {str(e)}")
            raise
