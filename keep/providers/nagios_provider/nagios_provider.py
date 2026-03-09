"""
Nagios Provider is a webhook-only provider for receiving Nagios alerts in Keep.
"""

from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  To send alerts from Nagios to Keep, configure a custom notification command that posts to the Keep webhook:

  ```bash
  define command{
    command_name    notify-keep
    command_line    /usr/bin/curl -X POST -H "Content-Type: application/json" -H "X-API-KEY: {api_key}" -d '{"host_name":"$HOSTNAME$","host_state":"$HOSTSTATE$","host_output":"$HOSTOUTPUT$","service_description":"$SERVICEDESC$","service_state":"$SERVICESTATE$","service_output":"$SERVICEOUTPUT$","notification_type":"$NOTIFICATIONTYPE$"}' {keep_webhook_api_url}
  }
  ```
    """

    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "service"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No validation required for Nagios provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        host_name = event.get("host_name")
        host_state = event.get("host_state")
        host_output = event.get("host_output")
        service_description = event.get("service_description")
        service_state = event.get("service_state")
        service_output = event.get("service_output")
        notification_type = event.get("notification_type")

        state = service_state or host_state or "UNKNOWN"
        severity = NagiosProvider.SEVERITY_MAP.get(
            state,
            AlertSeverity.CRITICAL if state in {"DOWN", "UNREACHABLE"} else AlertSeverity.INFO,
        )
        status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        description = service_output or host_output
        alert_id = (
            f"{host_name}:{service_description}" if service_description else host_name
        )
        alert_name = (
            f"{host_name} - {service_description}"
            if service_description
            else (host_name or "Nagios alert")
        )

        alert = AlertDto(
            id=alert_id,
            name=alert_name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=event.get("lastReceived")
            or event.get("timestamp")
            or datetime.now(timezone.utc).isoformat(),
            host=host_name,
            service=service_description,
            host_state=host_state,
            host_output=host_output,
            service_state=service_state,
            service_output=service_output,
            notification_type=notification_type,
            source=["nagios"],
        )
        alert.fingerprint = NagiosProvider.get_alert_fingerprint(
            alert, fingerprint_fields=NagiosProvider.FINGERPRINT_FIELDS
        )

        return alert


if __name__ == "__main__":
    pass
