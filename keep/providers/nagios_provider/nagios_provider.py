"""
Nagios is a widely-used open source monitoring tool for systems, networks, and infrastructure.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  1. Nagios supports custom notification commands.
  2. Define a new command in your Nagios configuration (e.g., `/usr/local/nagios/etc/objects/commands.cfg`):
     ```
     define command {{
         command_name    notify-keep
         command_line    /usr/bin/curl -s -X POST \\
           -H "Content-Type: application/json" \\
           -H "X-API-KEY: {api_key}" \\
           {keep_webhook_api_url} \\
           -d '{{"host_name":"$HOSTNAME$","service_description":"$SERVICEDESC$","state":"$SERVICESTATE$","state_type":"$SERVICESTATETYPE$","plugin_output":"$SERVICEOUTPUT$","long_plugin_output":"$LONGSERVICEOUTPUT$","notification_type":"$NOTIFICATIONTYPE$","host_state":"$HOSTSTATE$","host_address":"$HOSTADDRESS$","timestamp":"$TIMET$","current_attempt":"$SERVICEATTEMPT$","max_attempts":"$MAXSERVICEATTEMPTS$","duration":"$SERVICEDURATION$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$","acknowledgement_author":"$NOTIFICATIONAUTHORALIAS$","acknowledgement_comment":"$NOTIFICATIONCOMMENT$","service_url":"$SERVICEACTIONURL$"}}'
     }}
     ```
  3. Also define a host notification command:
     ```
     define command {{
         command_name    notify-keep-host
         command_line    /usr/bin/curl -s -X POST \\
           -H "Content-Type: application/json" \\
           -H "X-API-KEY: {api_key}" \\
           {keep_webhook_api_url} \\
           -d '{{"host_name":"$HOSTNAME$","state":"$HOSTSTATE$","state_type":"$HOSTSTATETYPE$","plugin_output":"$HOSTOUTPUT$","long_plugin_output":"$LONGHOSTOUTPUT$","notification_type":"$NOTIFICATIONTYPE$","host_address":"$HOSTADDRESS$","timestamp":"$TIMET$","current_attempt":"$HOSTATTEMPT$","max_attempts":"$MAXHOSTATTEMPTS$","duration":"$HOSTDURATION$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$","acknowledgement_author":"$NOTIFICATIONAUTHORALIAS$","acknowledgement_comment":"$NOTIFICATIONCOMMENT$"}}'
     }}
     ```
  4. Assign the notification commands to your contacts:
     ```
     define contact {{
         ...
         service_notification_commands   notify-keep
         host_notification_commands      notify-keep-host
     }}
     ```
  5. Restart Nagios to apply changes: `sudo systemctl restart nagios`
  6. Now Nagios will send alerts to Keep.
  """

    # Nagios service states
    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    # Nagios host states
    HOST_SEVERITIES_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "UP": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    NOTIFICATION_TYPE_STATUS_MAP = {
        "RECOVERY": AlertStatus.RESOLVED,
        "PROBLEM": AlertStatus.FIRING,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host_name", "service_description"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config():
        """
        No validation required for Nagios provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios notification into an AlertDto.
        Handles both host and service notifications.
        """

        def _get(key):
            val = event.get(key)
            if val is None or val == "":
                return None
            return val

        host_name = _get("host_name") or "unknown"
        service_description = _get("service_description")
        state = _get("state") or _get("host_state") or "UNKNOWN"
        notification_type = _get("notification_type")
        is_host_alert = service_description is None

        # Determine severity
        if is_host_alert:
            severity = NagiosProvider.HOST_SEVERITIES_MAP.get(
                state, AlertSeverity.WARNING
            )
        else:
            severity = NagiosProvider.SEVERITIES_MAP.get(
                state, AlertSeverity.WARNING
            )

        # Determine status from notification type first, then state
        if notification_type and notification_type in NagiosProvider.NOTIFICATION_TYPE_STATUS_MAP:
            status = NagiosProvider.NOTIFICATION_TYPE_STATUS_MAP[notification_type]
        else:
            status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Parse timestamp
        timestamp = _get("timestamp")
        if timestamp:
            try:
                dt_object = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                last_received = dt_object.isoformat()
            except (ValueError, OSError):
                last_received = datetime.now(timezone.utc).isoformat()
        else:
            last_received = datetime.now(timezone.utc).isoformat()

        # Build description
        if is_host_alert:
            description = f"Host {host_name} is {state}"
            name = f"host-{host_name}"
        else:
            description = f"{service_description} on {host_name} is {state}"
            name = f"{host_name}-{service_description}"

        alert = AlertDto(
            id=name,
            name=name,
            description=description,
            severity=severity,
            status=status,
            host=host_name,
            address=_get("host_address"),
            service=service_description,
            source=["nagios"],
            output=_get("plugin_output"),
            long_output=_get("long_plugin_output"),
            notification_type=notification_type,
            state_type=_get("state_type"),
            current_attempt=_get("current_attempt"),
            max_attempts=_get("max_attempts"),
            duration=_get("duration"),
            contact_name=_get("contact_name"),
            contact_email=_get("contact_email"),
            acknowledgement_author=_get("acknowledgement_author"),
            acknowledgement_comment=_get("acknowledgement_comment"),
            path_url=_get("service_url"),
            lastReceived=last_received,
        )

        return alert


if __name__ == "__main__":
    pass
