"""
Nagios is a monitoring tool for Infrastructure and Application Monitoring.
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
  ## Configuring Nagios to Send Alerts to Keep

  Nagios can send alerts to Keep via webhook using a custom notification command.

  ### Step 1: Create a Notification Command

  Add the following command definition to your Nagios configuration (e.g., `/usr/local/nagios/etc/objects/commands.cfg`):

  ```
  define command {{
      command_name    notify-keep-host
      command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -d '{{"host_name": "$HOSTNAME$", "host_alias": "$HOSTALIAS$", "host_address": "$HOSTADDRESS$", "state": "$HOSTSTATE$", "state_type": "$HOSTSTATETYPE$", "output": "$HOSTOUTPUT$", "long_output": "$LONGHOSTOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$"}}' \\
        "{keep_webhook_api_url}?api_key={api_key}"
  }}

  define command {{
      command_name    notify-keep-service
      command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -d '{{"host_name": "$HOSTNAME$", "host_alias": "$HOSTALIAS$", "host_address": "$HOSTADDRESS$", "service_description": "$SERVICEDESC$", "state": "$SERVICESTATE$", "state_type": "$SERVICESTATETYPE$", "output": "$SERVICEOUTPUT$", "long_output": "$LONGSERVICEOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$"}}' \\
        "{keep_webhook_api_url}?api_key={api_key}"
  }}
  ```

  ### Step 2: Create a Contact for Keep

  Add a contact definition that uses the Keep notification commands:

  ```
  define contact {{
      contact_name                    keep
      alias                           Keep Webhook
      service_notification_period     24x7
      host_notification_period        24x7
      service_notification_options    w,u,c,r
      host_notification_options       d,u,r
      service_notification_commands   notify-keep-service
      host_notification_commands      notify-keep-host
  }}
  ```

  ### Step 3: Add the Contact to a Contact Group

  Add the `keep` contact to an appropriate contact group:

  ```
  define contactgroup {{
      contactgroup_name   keep-notifications
      alias               Keep Notifications
      members             keep
  }}
  ```

  ### Step 4: Assign the Contact Group to Hosts/Services

  Add `contact_groups keep-notifications` to your host and service definitions, or use a template.

  ### Step 5: Restart Nagios

  ```
  sudo systemctl restart nagios
  ```

  Now Nagios will send alerts to Keep via webhook.
  """

    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        # Host states
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        # Service states
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host_name", "service_description"]

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
        """
        Format a Nagios webhook event into an AlertDto.
        Handles both host and service notifications.
        """

        def _get(key):
            value = event.get(key)
            if value is None or value == "":
                return None
            return value

        state = _get("state") or "UNKNOWN"
        host_name = _get("host_name")
        service_description = _get("service_description")
        notification_type = _get("notification_type")

        # Determine if this is a host or service alert
        is_host_alert = service_description is None

        # Build alert name
        if is_host_alert:
            name = f"Host {state}: {host_name}"
        else:
            name = f"{service_description} on {host_name}"

        # Parse timestamp
        last_received = None
        timestamp = _get("timestamp")
        if timestamp:
            try:
                ts = int(timestamp)
                dt_object = datetime.fromtimestamp(ts, tz=timezone.utc)
                last_received = dt_object.isoformat()
            except (ValueError, OSError):
                logger.warning(f"Failed to parse timestamp: {timestamp}")

        alert = AlertDto(
            id=f"{host_name}:{service_description or 'HOST'}"
            if host_name
            else None,
            name=name,
            description=_get("output"),
            severity=NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
            status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
            host=host_name,
            service=service_description,
            source=["nagios"],
            output=_get("output"),
            long_output=_get("long_output"),
            notification_type=notification_type,
            lastReceived=last_received,
            alias=_get("host_alias"),
            address=_get("host_address"),
            state_type=_get("state_type"),
        )

        return alert


if __name__ == "__main__":
    pass
