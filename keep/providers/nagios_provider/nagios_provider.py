"""
Nagios Provider is a class that allows to ingest alerts from Nagios Core and Nagios XI.

Nagios sends alerts to Keep via a webhook notification command that POSTs JSON data
whenever a host or service state changes.
"""

import dataclasses
import logging
from datetime import datetime, timezone

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

    nagios_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios Web UI URL (optional, used for generating alert links)",
            "hint": "https://nagios.example.com/nagios",
            "sensitive": False,
        },
        default="",
    )


class NagiosProvider(BaseProvider):
    """
    Receive alerts from Nagios (Core or XI) via webhook notifications.

    Nagios is configured with a notification command that sends JSON payloads
    to Keep's webhook endpoint using curl. This provider parses and normalises
    those payloads into Keep's AlertDto format.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["hostname", "service_description"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Nagios Webhook Integration

To send Nagios alerts to Keep, configure a notification command in your Nagios installation.

### 1. Define the notification commands

Add the following to your Nagios command configuration (e.g. `/usr/local/nagios/etc/objects/commands.cfg`):

**Host notifications:**

```
define command {{
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        -d '{{ \\
            "object_type": "host", \\
            "hostname": "$HOSTNAME$", \\
            "host_alias": "$HOSTALIAS$", \\
            "host_address": "$HOSTADDRESS$", \\
            "host_state": "$HOSTSTATE$", \\
            "host_state_type": "$HOSTSTATETYPE$", \\
            "host_output": "$HOSTOUTPUT$", \\
            "long_host_output": "$LONGHOSTOUTPUT$", \\
            "notification_type": "$NOTIFICATIONTYPE$", \\
            "notification_author": "$NOTIFICATIONAUTHOR$", \\
            "notification_comment": "$NOTIFICATIONCOMMENT$", \\
            "date_time": "$LONGDATETIME$", \\
            "host_duration": "$HOSTDURATION$" \\
        }}' \\
        '{keep_webhook_api_url}'
}}
```

**Service notifications:**

```
define command {{
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        -d '{{ \\
            "object_type": "service", \\
            "hostname": "$HOSTNAME$", \\
            "host_alias": "$HOSTALIAS$", \\
            "host_address": "$HOSTADDRESS$", \\
            "service_description": "$SERVICEDESC$", \\
            "service_state": "$SERVICESTATE$", \\
            "service_state_type": "$SERVICESTATETYPE$", \\
            "service_output": "$SERVICEOUTPUT$", \\
            "long_service_output": "$LONGSERVICEOUTPUT$", \\
            "notification_type": "$NOTIFICATIONTYPE$", \\
            "notification_author": "$NOTIFICATIONAUTHOR$", \\
            "notification_comment": "$NOTIFICATIONCOMMENT$", \\
            "date_time": "$LONGDATETIME$", \\
            "service_duration": "$SERVICEDURATION$" \\
        }}' \\
        '{keep_webhook_api_url}'
}}
```

### 2. Create a contact for Keep

```
define contact {{
    contact_name                    keep
    alias                           Keep Alert Manager
    service_notification_period     24x7
    host_notification_period        24x7
    service_notification_options    w,u,c,r,f,s
    host_notification_options       d,u,r,f,s
    service_notification_commands   notify-keep-service
    host_notification_commands      notify-keep-host
}}
```

### 3. Add the contact to a contact group

```
define contactgroup {{
    contactgroup_name    keep-notifications
    alias                Keep Notifications
    members              keep
}}
```

Add `keep-notifications` to the `contact_groups` directive of the hosts and services you want to monitor.

### 4. Restart Nagios

```bash
sudo systemctl restart nagios
```
"""

    # Nagios host states
    HOST_SEVERITY_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    # Nagios service states
    SERVICE_SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    # Map Nagios states to Keep statuses
    HOST_STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    SERVICE_STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    # Notification types that indicate resolution
    RECOVERY_NOTIFICATION_TYPES = {"RECOVERY", "UP", "OK"}
    # Notification types that indicate acknowledgement
    ACKNOWLEDGEMENT_TYPES = {"ACKNOWLEDGEMENT"}

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios webhook event into an AlertDto.

        Nagios sends different fields for host vs service alerts.
        We normalise both into a consistent AlertDto.
        """
        object_type = event.get("object_type", "").lower()
        notification_type = event.get("notification_type", "").upper()

        hostname = event.get("hostname", "")
        host_alias = event.get("host_alias", "")
        host_address = event.get("host_address", "")
        service_description = event.get("service_description", "")

        # Determine state, severity, and status based on object type
        if object_type == "service":
            state = event.get("service_state", "UNKNOWN").upper()
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(
                state, AlertSeverity.INFO
            )
            status = NagiosProvider.SERVICE_STATUS_MAP.get(
                state, AlertStatus.FIRING
            )
            output = event.get("service_output", "")
            long_output = event.get("long_service_output", "")
            name = f"{hostname}/{service_description}"
            duration = event.get("service_duration", "")
            state_type = event.get("service_state_type", "")
        else:
            # Host alert
            state = event.get("host_state", "UP").upper()
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(
                state, AlertSeverity.INFO
            )
            status = NagiosProvider.HOST_STATUS_MAP.get(
                state, AlertStatus.FIRING
            )
            output = event.get("host_output", "")
            long_output = event.get("long_host_output", "")
            name = hostname
            service_description = ""
            duration = event.get("host_duration", "")
            state_type = event.get("host_state_type", "")

        # Override status based on notification type
        if notification_type in NagiosProvider.RECOVERY_NOTIFICATION_TYPES:
            status = AlertStatus.RESOLVED
        elif notification_type in NagiosProvider.ACKNOWLEDGEMENT_TYPES:
            status = AlertStatus.ACKNOWLEDGED

        # Build a unique alert ID
        alert_id = f"nagios-{hostname}"
        if service_description:
            alert_id += f"-{service_description}"

        # Parse date_time
        date_time_str = event.get("date_time", "")
        last_received = datetime.now(tz=timezone.utc).isoformat()
        if date_time_str:
            # Nagios $LONGDATETIME$ format: "Thu Jan 02 15:30:00 CET 2025"
            # Try multiple formats
            formats = [
                "%a %b %d %H:%M:%S %Z %Y",
                "%a %b %d %H:%M:%S %z %Y",
                "%m-%d-%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_time_str, fmt)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    last_received = parsed.astimezone(timezone.utc).isoformat()
                    break
                except ValueError:
                    continue

        # Build description
        description = output
        if long_output:
            description = f"{output}\n{long_output}"

        # Generate URL if nagios_url is configured
        url = None
        if provider_instance and hasattr(provider_instance, "authentication_config"):
            nagios_url = getattr(
                provider_instance.authentication_config, "nagios_url", ""
            )
            if nagios_url:
                nagios_url = nagios_url.rstrip("/")
                if object_type == "service" and service_description:
                    url = (
                        f"{nagios_url}/cgi-bin/extinfo.cgi"
                        f"?type=2&host={hostname}&service={service_description}"
                    )
                else:
                    url = (
                        f"{nagios_url}/cgi-bin/extinfo.cgi?type=1&host={hostname}"
                    )

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["nagios"],
            pushed=True,
            hostname=hostname,
            host_alias=host_alias,
            ip_address=host_address,
            service=service_description or hostname,
            service_description=service_description,
            message=output,
            url=url,
            notification_type=notification_type,
            state=state,
            state_type=state_type,
            duration=duration,
            notification_author=event.get("notification_author", ""),
            notification_comment=event.get("notification_comment", ""),
            environment=event.get("environment", "unknown"),
        )


if __name__ == "__main__":
    pass
