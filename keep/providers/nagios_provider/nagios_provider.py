"""
Nagios Provider is a class that allows to receive alerts from Nagios
via webhook notifications.
"""

import dataclasses
import logging

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios URL",
            "hint": "https://nagios.example.com/nagios",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  1. Nagios can send notifications to Keep using a custom notification command.
  2. In your Nagios configuration, define a new command that sends a POST request to Keep's webhook URL.
  3. The webhook URL is: {keep_webhook_api_url}
  4. The API key is: {api_key}
  5. See [Keep documentation](https://docs.keephq.dev/providers/documentation/nagios-provider) for detailed setup instructions.
  """

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    NOTIFICATION_TYPE_MAP = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
        "DOWNTIMECANCELLED": AlertStatus.RESOLVED,
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No validation required for Nagios provider.
        """
        pass

    def dispose(self):
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook notification payload into a Keep AlertDto.

        Nagios sends different macros for host vs. service notifications.
        We handle both cases here.
        """
        host_name = event.get("host_name", event.get("hostname", ""))
        service_desc = event.get("service_description", event.get("service", ""))
        state = event.get("state", event.get("service_state", event.get("host_state", "UNKNOWN")))
        output = event.get("output", event.get("service_output", event.get("host_output", "")))
        notification_type = event.get("notification_type", "")
        address = event.get("host_address", event.get("address", ""))
        timestamp = event.get("timestamp", event.get("long_date_time", None))

        # Build a stable alert id from host + service
        if service_desc:
            alert_id = f"{host_name}/{service_desc}"
            alert_name = service_desc
        else:
            alert_id = host_name
            alert_name = host_name

        # Determine status: prefer notification_type, fall back to state
        status = NagiosProvider.NOTIFICATION_TYPE_MAP.get(notification_type)
        if status is None:
            status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Check for acknowledged state from event data
        acknowledged = event.get("problem_acknowledged", event.get("acknowledged", "0"))
        if str(acknowledged) == "1":
            status = AlertStatus.ACKNOWLEDGED

        severity = NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO)

        alert = AlertDto(
            id=alert_id,
            name=alert_name,
            description=output,
            severity=severity,
            status=status,
            host=host_name,
            address=address,
            service=service_desc if service_desc else None,
            source=["nagios"],
            notification_type=notification_type,
            lastReceived=timestamp,
        )

        return alert


if __name__ == "__main__":
    pass
