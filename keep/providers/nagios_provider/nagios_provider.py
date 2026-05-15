"""
Nagios Provider is a class that provides a way to receive alerts from Nagios
using webhook notifications.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class NagiosProvider(BaseProvider):
    """
    Receive Nagios host and service notifications into Keep via webhooks.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, configure a custom notification command:

1. Create a notification command that POSTs JSON to `{keep_webhook_api_url}`.
2. Add header `X-API-KEY` with your Keep API key (webhook role).
3. Use Nagios macros such as `$NOTIFICATIONTYPE$`, `$HOSTNAME$`, `$HOSTSTATE$`,
   `$HOSTOUTPUT$`, `$SERVICEDESC$`, `$SERVICESTATE$`, and `$SERVICEOUTPUT$` to
   build the JSON payload.
4. Attach the command to your host and/or service notification definitions.
5. For a complete example, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/nagios-provider).
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True

    HOST_STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    HOST_SEVERITY_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
    }

    SERVICE_STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    SERVICE_SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

    def validate_config(self):
        """
        Nagios webhook integration does not require provider-side configuration.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Nagios notification payload into Keep alert format.

        Supported payloads are intentionally simple and map closely to Nagios
        host/service notification macros configured in the webhook command.
        """
        alert_type = (event.get("alert_type") or "service").lower()

        if alert_type == "host":
            state = event.get("host_state", "DOWN")
            output = event.get("host_output", "No output provided")
            return AlertDto(
                id=event.get("host_name"),
                name=event.get("host_display_name") or event.get("host_name"),
                status=NagiosProvider.HOST_STATUS_MAP.get(state, AlertStatus.FIRING),
                severity=NagiosProvider.HOST_SEVERITY_MAP.get(
                    state, AlertSeverity.CRITICAL
                ),
                description=output,
                source=["nagios"],
                hostname=event.get("host_name"),
                state=state,
                lastReceived=event.get("timestamp"),
                timestamp=event.get("timestamp"),
                notification_type=event.get("notification_type"),
                raw_output=output,
                host_address=event.get("host_address"),
            )

        state = event.get("service_state", "CRITICAL")
        output = event.get("service_output", "No output provided")
        return AlertDto(
            id=event.get("service_name") or event.get("host_name"),
            name=event.get("service_display_name") or event.get("service_name"),
            status=NagiosProvider.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING),
            severity=NagiosProvider.SERVICE_SEVERITY_MAP.get(
                state, AlertSeverity.CRITICAL
            ),
            description=output,
            source=["nagios"],
            hostname=event.get("host_name"),
            host_address=event.get("host_address"),
            service_name=event.get("service_name"),
            check_command=event.get("service_check_command"),
            state=state,
            lastReceived=event.get("timestamp"),
            timestamp=event.get("timestamp"),
            notification_type=event.get("notification_type"),
            raw_output=output,
            current_attempt=event.get("service_attempt"),
            state_type=event.get("service_state_type"),
            performance_data=event.get("service_perfdata"),
        )


if __name__ == "__main__":
    pass
