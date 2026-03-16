"""
Nagios provider for Keep.
Supports both Nagios Core and Nagios XI via webhook-based alert ingestion
and pull-based alert retrieval (Nagios XI REST API).
"""

import dataclasses
import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Configuration for Nagios XI API access (optional — only needed for pull mode).
    """

    nagios_url: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios XI Base URL",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )
    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios XI API Key",
            "hint": "Navigate to Admin > Manage API Keys",
            "sensitive": True,
        },
    )


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios Core or Nagios XI into Keep."""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "service", "name"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Nagios XI API key is valid (optional — only for pull mode).",
            mandatory=False,
        ),
    ]

    # Nagios service states -> Keep severity
    SEVERITIES_MAP = {
        # Service states
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        # Host states mapped to severity
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    # Nagios states -> Keep status
    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
    }

    # Notification type -> Keep status
    NOTIFICATION_TYPE_MAP = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "FLAPPINGDISABLED": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
        "DOWNTIMECANCELLED": AlertStatus.RESOLVED,
    }

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Webhook Setup for Nagios

Keep accepts alerts from both **Nagios Core** and **Nagios XI** via webhook notifications.

### Nagios Core / Nagios XI — curl-based notification commands

1. Define a notification command in your Nagios configuration:

**For service notifications** (`/usr/local/nagios/etc/objects/commands.cfg`):

```
define command {{
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        "{keep_webhook_api_url}" \\
        -d '{{"notification_type":"$NOTIFICATIONTYPE$","host":"$HOSTNAME$","host_alias":"$HOSTALIAS$","host_address":"$HOSTADDRESS$","service":"$SERVICEDESC$","state":"$SERVICESTATE$","output":"$SERVICEOUTPUT$","long_output":"$LONGSERVICEOUTPUT$","timestamp":"$TIMET$","attempt":"$SERVICEATTEMPT$","max_attempts":"$MAXSERVICEATTEMPTS$","state_type":"$SERVICESTATETYPE$","notification_author":"$NOTIFICATIONAUTHOR$","notification_comment":"$NOTIFICATIONCOMMENT$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$"}}'
}}
```

**For host notifications**:

```
define command {{
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        "{keep_webhook_api_url}" \\
        -d '{{"notification_type":"$NOTIFICATIONTYPE$","host":"$HOSTNAME$","host_alias":"$HOSTALIAS$","host_address":"$HOSTADDRESS$","state":"$HOSTSTATE$","output":"$HOSTOUTPUT$","long_output":"$LONGHOSTOUTPUT$","timestamp":"$TIMET$","attempt":"$HOSTATTEMPT$","max_attempts":"$MAXHOSTATTEMPTS$","state_type":"$HOSTSTATETYPE$","notification_author":"$NOTIFICATIONAUTHOR$","notification_comment":"$NOTIFICATIONCOMMENT$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$"}}'
}}
```

2. Assign the notification commands to a contact:

```
define contact {{
    contact_name                    keep
    alias                           Keep AIOps
    service_notification_commands   notify-keep-service
    host_notification_commands      notify-keep-host
    service_notification_period     24x7
    host_notification_period        24x7
    service_notification_options    w,u,c,r,f,s
    host_notification_options       d,u,r,f,s
    email                           keep@localhost
}}
```

3. Add the contact to relevant contact groups or hosts/services.

### Nagios XI — Alternative via XI API

If you are using Nagios XI, you can also configure Keep in pull mode by providing the Nagios XI URL and API key in the provider settings. Keep will periodically fetch current problems from the Nagios XI API.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validate and parse configuration. Auth config is optional (webhook-only mode).
        """
        self.authentication_config = None
        if self.config.authentication:
            self.authentication_config = NagiosProviderAuthConfig(
                **self.config.authentication
            )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        if (
            self.authentication_config
            and self.authentication_config.nagios_url
            and self.authentication_config.api_key
        ):
            try:
                response = requests.get(
                    f"{self.authentication_config.nagios_url}/api/v1/objects/hoststatus",
                    params={
                        "apikey": self.authentication_config.api_key,
                        "records": "1:1",
                    },
                    verify=False,
                    timeout=10,
                )
                if response.status_code == 200:
                    scopes["authenticated"] = True
                else:
                    scopes["authenticated"] = (
                        f"API returned status {response.status_code}"
                    )
            except Exception as e:
                scopes["authenticated"] = str(e)
        else:
            scopes["authenticated"] = "Not configured (webhook-only mode)"
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull current problems from Nagios XI API.
        Requires nagios_url and api_key in authentication config.
        """
        if not (
            self.authentication_config
            and self.authentication_config.nagios_url
            and self.authentication_config.api_key
        ):
            return []

        alerts = []
        base_url = str(self.authentication_config.nagios_url).rstrip("/")
        api_key = self.authentication_config.api_key

        # Fetch service problems
        try:
            response = requests.get(
                f"{base_url}/api/v1/objects/servicestatus",
                params={
                    "apikey": api_key,
                    "current_state": "in:1,2,3",  # WARNING, CRITICAL, UNKNOWN
                },
                verify=False,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for record in data.get("servicestatus", []):
                state = record.get("current_state", "0")
                state_text = {
                    "0": "OK",
                    "1": "WARNING",
                    "2": "CRITICAL",
                    "3": "UNKNOWN",
                }.get(str(state), "UNKNOWN")

                alert = AlertDto(
                    id=f"nagios-svc-{record.get('host_name', '')}-{record.get('name', '')}",
                    name=record.get("name", ""),
                    description=record.get("status_text", ""),
                    severity=self.SEVERITIES_MAP.get(
                        state_text, AlertSeverity.INFO
                    ),
                    status=self.STATUS_MAP.get(state_text, AlertStatus.FIRING),
                    host=record.get("host_name", ""),
                    service=record.get("name", ""),
                    source=["nagios"],
                    lastReceived=self._parse_xi_timestamp(
                        record.get("last_check")
                    ),
                    state_type=record.get("state_type", ""),
                    current_attempt=record.get("current_check_attempt", ""),
                    max_attempts=record.get("max_check_attempts", ""),
                    output=record.get("status_text", ""),
                )
                alerts.append(alert)

        except Exception:
            logger.exception("Error fetching service alerts from Nagios XI")

        # Fetch host problems
        try:
            response = requests.get(
                f"{base_url}/api/v1/objects/hoststatus",
                params={
                    "apikey": api_key,
                    "current_state": "in:1,2",  # DOWN, UNREACHABLE
                },
                verify=False,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for record in data.get("hoststatus", []):
                state = record.get("current_state", "0")
                state_text = {"0": "UP", "1": "DOWN", "2": "UNREACHABLE"}.get(
                    str(state), "DOWN"
                )

                alert = AlertDto(
                    id=f"nagios-host-{record.get('name', '')}",
                    name=f"Host {state_text}",
                    description=record.get("status_text", ""),
                    severity=self.SEVERITIES_MAP.get(
                        state_text, AlertSeverity.CRITICAL
                    ),
                    status=self.STATUS_MAP.get(state_text, AlertStatus.FIRING),
                    host=record.get("name", ""),
                    address=record.get("address", ""),
                    source=["nagios"],
                    lastReceived=self._parse_xi_timestamp(
                        record.get("last_check")
                    ),
                    state_type=record.get("state_type", ""),
                    current_attempt=record.get("current_check_attempt", ""),
                    max_attempts=record.get("max_check_attempts", ""),
                    output=record.get("status_text", ""),
                )
                alerts.append(alert)

        except Exception:
            logger.exception("Error fetching host alerts from Nagios XI")

        return alerts

    @staticmethod
    def _parse_xi_timestamp(timestamp_str: str | None) -> str | None:
        """Convert Nagios XI timestamp to ISO format."""
        if not timestamp_str:
            return None
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except (ValueError, TypeError):
            return timestamp_str

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a webhook event from Nagios into an AlertDto.
        Handles both host and service notifications from Nagios Core and XI.
        """
        notification_type = event.get("notification_type", "PROBLEM").upper()
        state = event.get("state", "").upper()
        host = event.get("host", "")
        service = event.get("service", "")
        output = event.get("output", "")
        long_output = event.get("long_output", "")

        # Determine if this is a host or service alert
        is_host_alert = not service

        # Build alert ID
        if is_host_alert:
            alert_id = f"nagios-host-{host}"
            name = f"Host {state}" if state else f"Host {notification_type}"
        else:
            alert_id = f"nagios-svc-{host}-{service}"
            name = service

        # Determine status — notification_type takes precedence
        status = NagiosProvider.NOTIFICATION_TYPE_MAP.get(notification_type)
        if status is None:
            status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Determine severity from state
        severity = NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.WARNING)

        # Parse timestamp
        timestamp = event.get("timestamp")
        if timestamp:
            try:
                ts = int(timestamp)
                last_received = datetime.fromtimestamp(
                    ts, tz=timezone.utc
                ).isoformat()
            except (ValueError, TypeError, OSError):
                last_received = datetime.now(tz=timezone.utc).isoformat()
        else:
            last_received = datetime.now(tz=timezone.utc).isoformat()

        description = output
        if long_output:
            description = f"{output}\n{long_output}"

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            host=host,
            host_alias=event.get("host_alias", ""),
            address=event.get("host_address", ""),
            service=service if service else None,
            source=["nagios"],
            lastReceived=last_received,
            notification_type=notification_type,
            state=state,
            state_type=event.get("state_type", ""),
            attempt=event.get("attempt", ""),
            max_attempts=event.get("max_attempts", ""),
            output=output,
            long_output=long_output,
            contact_name=event.get("contact_name", ""),
            contact_email=event.get("contact_email", ""),
            notification_author=event.get("notification_author", ""),
            notification_comment=event.get("notification_comment", ""),
        )

        return alert


if __name__ == "__main__":
    pass
