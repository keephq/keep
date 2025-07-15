import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class NagiosProvider(BaseProvider):
    """Provider implementation for Nagios monitoring system.
    
    This provider handles the integration with Nagios monitoring system,
    processing incoming alerts and converting them to Keep's alert format.
    """

    PROVIDER_DISPLAY_NAME: str = "Nagios"
    PROVIDER_TAGS: list[str] = ["alert", "incident"]
    PROVIDER_CATEGORY: list[str] = ["Monitoring"]
    PROVIDER_ICON = "nagios-icon.png"

    _state_mapping: Dict[str, AlertSeverity] = {
        "OK": AlertSeverity.LOW,
        "WARNING": AlertSeverity.WARNING,
        "UNKNOWN": AlertSeverity.INFO,
        "CRITICAL": AlertSeverity.HIGH,
        "UP": AlertSeverity.LOW,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL
    }


    def __init__(
        self, 
        context_manager: Any, 
        provider_id: str, 
        config: ProviderConfig
    ) -> None:
        """Initialize Nagios provider.

        Args:
            context_manager: The context manager instance
            provider_id: Unique provider identifier
            config: Provider configuration parameters
        """
        super().__init__(context_manager, provider_id, config)


    def _generate_alert_id(self, event: Dict[str, Any]) -> str:
        """Generate unique alert ID from event data.

        Args:
            event: The Nagios event data

        Returns:
            str: MD5 hash of key event fields
        """
        key_fields = {
            "host_name": event.get("host_name", ""),
            "service_description": event.get("service_description", ""),
            "timestamp": event.get("timestamp", "")
        }
        hash_input = json.dumps(key_fields, sort_keys=True).encode()
        return hashlib.md5(hash_input).hexdigest()


    def _validate_timestamp(self, timestamp: Optional[str]) -> bool:
        """Validate timestamp format.

        Args:
            timestamp: ISO format timestamp string

        Returns:
            bool: True if timestamp is valid, False otherwise
        """
        if not timestamp:
            return False
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False


    def _determine_severity(self, event: Dict[str, Any]) -> AlertSeverity:
        """Determine alert severity from event state.

        Args:
            event: The Nagios event data

        Returns:
            AlertSeverity: Determined severity level
        """
        if "service_state" in event:
            service_state = event.get("service_state")
            return self._state_mapping.get(service_state, AlertSeverity.INFO)
        elif "host_state" in event:
            host_state = event.get("host_state")
            return self._state_mapping.get(host_state, AlertSeverity.INFO)
        return AlertSeverity.INFO


    def _format_alert(self, event: Dict[str, Any]) -> AlertDto:
        """Format Nagios event into Keep alert format.

        Args:
            event: The Nagios event data

        Returns:
            AlertDto: Formatted alert object

        Raises:
            ValueError: If required fields are missing
        """
        try:
            host_name = event.get("host_name")
            if not host_name:
                raise ValueError("Missing required field: host_name")

            timestamp = event.get("timestamp")
            if not self._validate_timestamp(timestamp):
                raise ValueError("Invalid or missing timestamp")

            service_description = event.get("service_description")
            description = event.get("output", "No description provided")
            
            severity = self._determine_severity(event)
            
            # Status Determination ...
            status = AlertStatus.FIRING
            if "service_state" in event and event["service_state"] == "OK":
                status = AlertStatus.RESOLVED
            elif "host_state" in event and event["host_state"] == "UP":
                status = AlertStatus.RESOLVED
            
            alert_id = event.get("id") or self._generate_alert_id(event)

            filtered_event = {
                k: v for k, v in event.items()
                if k in [
                    "service_state",
                    "host_state", 
                    "output"
                ]
            }

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
                **filtered_event
            )
            
        except ValueError as err:
            logger.error("Invalid Nagios alert data: %s", str(err))
            raise
        except Exception as err:
            logger.error("Error formatting Nagios alert: %s", str(err))
            raise