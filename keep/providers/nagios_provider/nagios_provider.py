"""
Nagios provider for Keep.

Nagios is a widely-used open-source infrastructure and network monitoring system.
This provider receives Nagios alert notifications via HTTP webhook using Nagios's
built-in notification command or a custom event broker script that POSTs alerts
to Keep.

This provider supports:
- Push: receives Nagios host and service alert notifications via webhook
- Parse both host checks (ping, reachability) and service checks (CPU, disk, HTTP, etc.)
- Maps Nagios states (OK, WARNING, CRITICAL, UNKNOWN, UP, DOWN, UNREACHABLE)

References:
- https://www.nagios.org/documentation/
- https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/notifications.html
"""

import dataclasses
import datetime
import uuid

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """Authentication configuration for the Nagios webhook provider."""

    webhook_api_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Optional API key to authenticate incoming Nagios webhook requests",
            "sensitive": True,
            "hint": "Leave empty if you rely on network-level access controls",
        },
    )


class NagiosProvider(BaseProvider):
    """Receive host and service alerts from Nagios into Keep via webhook."""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    webhook_description = (
        "Configure Nagios to POST host/service notifications to Keep using a "
        "custom notification command that calls a small shell script."
    )
    webhook_template = ""
    webhook_markdown = """
To forward Nagios alerts to Keep, add a notification command to your Nagios config
that sends an HTTP POST to Keep whenever a host or service changes state.

**1. Create a notification script** (e.g. `/usr/local/nagios/libexec/notify_keep.sh`):

```bash
#!/bin/bash
# Usage: notify_keep.sh <type> <host> <state> <service> <output> <notification_type>
TYPE="$1"          # HOST or SERVICE
HOST="$2"
STATE="$3"
SERVICE="$4"
OUTPUT="$5"
NOTIF_TYPE="$6"    # PROBLEM / RECOVERY / ACKNOWLEDGEMENT

curl -s -X POST '{keep_webhook_api_url}' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: {api_key}' \\
  -d "{{
    \\"check_type\\": \\"$TYPE\\",
    \\"hostname\\": \\"$HOST\\",
    \\"state\\": \\"$STATE\\",
    \\"service_description\\": \\"$SERVICE\\",
    \\"plugin_output\\": \\"$OUTPUT\\",
    \\"notification_type\\": \\"$NOTIF_TYPE\\"
  }}"
```

**2. Register the commands in `commands.cfg`:**

```cfg
define command {
  command_name  notify-keep-host
  command_line  /usr/local/nagios/libexec/notify_keep.sh HOST $HOSTNAME$ $HOSTSTATE$ "" "$HOSTOUTPUT$" $NOTIFICATIONTYPE$
}

define command {
  command_name  notify-keep-service
  command_line  /usr/local/nagios/libexec/notify_keep.sh SERVICE $HOSTNAME$ $SERVICESTATE$ $SERVICEDESC$ "$SERVICEOUTPUT$" $NOTIFICATIONTYPE$
}
```

**3. Assign the commands in your contact definition:**

```cfg
define contact {
  contact_name                    keep-notify
  host_notification_commands      notify-keep-host
  service_notification_commands   notify-keep-service
  host_notification_period        24x7
  service_notification_period     24x7
  host_notification_options       d,u,r
  service_notification_options    w,u,c,r
}
```

**4. Add `keep-notify` to the contacts for hosts/services you want to forward.**
"""

    # Nagios host states
    HOST_SEVERITY_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    HOST_STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    # Nagios service states
    SERVICE_SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.HIGH,
    }

    SERVICE_STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    # Notification types → Keep status overrides
    NOTIFICATION_TYPE_STATUS_MAP = {
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "PROBLEM": AlertStatus.FIRING,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse a Nagios webhook payload into an AlertDto.

        The payload may come from a custom notify script or a Nagios event broker.
        Expected fields (all optional with sensible defaults):
          check_type        - "HOST" or "SERVICE" (defaults to SERVICE if service_description present)
          hostname          - host being checked
          state             - "OK"/"WARNING"/"CRITICAL"/"UNKNOWN"/"UP"/"DOWN"/"UNREACHABLE"
          service_description - name of the service (empty for host checks)
          plugin_output     - first line of check plugin output
          long_plugin_output - full plugin output
          notification_type - "PROBLEM"/"RECOVERY"/"ACKNOWLEDGEMENT"/etc.
          host_address      - IP address of the host
          check_attempt     - current check attempt
          max_check_attempts - max retries before hard state
          contact_email     - notified contact e-mail
        """
        check_type = event.get("check_type", "").upper()
        hostname = event.get("hostname", "unknown-host")
        state = (event.get("state", "") or event.get("hoststate", "") or event.get("servicestate", "")).upper()
        service = event.get("service_description", "") or event.get("servicedesc", "")
        plugin_output = event.get("plugin_output", "") or event.get("hostoutput", "") or event.get("serviceoutput", "")
        notification_type = (event.get("notification_type", "PROBLEM") or "PROBLEM").upper()

        # Determine whether this is a host or service check
        is_host_check = (check_type == "HOST") or (not service)

        # Build a stable alert name
        if service:
            alert_name = f"{hostname}/{service}"
        else:
            alert_name = f"{hostname}/host"

        # Map severity and status based on check type
        if is_host_check:
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(state, AlertSeverity.HIGH)
            status = NagiosProvider.HOST_STATUS_MAP.get(state, AlertStatus.FIRING)
        else:
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(state, AlertSeverity.HIGH)
            status = NagiosProvider.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING)

        # Notification type can override the derived status
        notif_status = NagiosProvider.NOTIFICATION_TYPE_STATUS_MAP.get(notification_type)
        if notif_status is not None:
            status = notif_status

        # Build a deterministic fingerprint from host + service name
        fp_string = f"nagios-{hostname}-{service or 'host'}"
        fingerprint = str(uuid.uuid5(uuid.NAMESPACE_DNS, fp_string))

        alert_dto = AlertDto(
            id=event.get("id", fingerprint),
            fingerprint=fingerprint,
            name=alert_name,
            description=plugin_output,
            status=status,
            severity=severity,
            source=["nagios"],
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            hostname=hostname,
            host_address=event.get("host_address", ""),
            service=service or None,
            state=state,
            notification_type=notification_type,
            check_attempt=event.get("check_attempt"),
            max_check_attempts=event.get("max_check_attempts"),
            long_plugin_output=event.get("long_plugin_output", ""),
            payload=event,
        )
        return alert_dto

    def dispose(self):
        pass
