"""
Nagios Provider is a class that allows to receive alerts from Nagios via webhook.
"""

import dataclasses
import logging
from datetime import datetime, timezone

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
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios URL",
            "hint": "https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios XI API Key (optional, for pulling alerts)",
            "hint": "Your Nagios XI REST API key",
            "sensitive": True,
        },
        default="",
    )


class NagiosProvider(BaseProvider):
    """
    Receive alerts from Nagios (Core & XI) into Keep.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "service", "name"]

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  ## Nagios Core Setup

  1. Create a webhook script on your Nagios server:

  ```bash
  #!/bin/bash
  # /usr/local/nagios/libexec/keep_webhook.sh

  KEEP_URL="$1"
  API_KEY="$2"

  # Read environment variables set by Nagios
  curl -s -X POST "$KEEP_URL" \\
    -H "Content-Type: application/json" \\
    -H "X-API-KEY: $API_KEY" \\
    -d '{
      "host": "'$NAGIOS_HOSTNAME'",
      "service": "'$NAGIOS_SERVICEDESC'",
      "status": "'$NAGIOS_SERVICESTATE'",
      "host_status": "'$NAGIOS_HOSTSTATE'",
      "output": "'$NAGIOS_SERVICEOUTPUT'",
      "long_output": "'$NAGIOS_LONGSERVICEOUTPUT'",
      "notification_type": "'$NAGIOS_NOTIFICATIONTYPE'",
      "attempt": "'$NAGIOS_SERVICEATTEMPT'",
      "max_attempts": "'$NAGIOS_MAXSERVICEATTEMPTS'",
      "event_time": "'$NAGIOS_TIMET'",
      "contact_name": "'$NAGIOS_CONTACTNAME'",
      "contact_email": "'$NAGIOS_CONTACTEMAIL'",
      "address": "'$NAGIOS_HOSTADDRESS'"
    }'
  ```

  2. Make it executable: `chmod +x /usr/local/nagios/libexec/keep_webhook.sh`

  3. Define a command in your Nagios config:

  ```
  define command {{
      command_name    notify-keep
      command_line    /usr/local/nagios/libexec/keep_webhook.sh "{keep_webhook_api_url}" "{api_key}"
  }}
  ```

  4. Add the command to your contact definition for service and host notifications.

  ## Nagios XI Setup

  Use the webhook configuration in Nagios XI admin panel to POST to: `{keep_webhook_api_url}`
  with the API key header `X-API-KEY: {api_key}`.
  """

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
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "PROBLEM": AlertStatus.FIRING,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
        "DOWNTIMECANCELLED": AlertStatus.RESOLVED,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connected",
            description="The provider is able to connect to Nagios",
            mandatory=False,
            documentation_url="https://www.nagios.org/documentation/",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        api_key = self.authentication_config.api_key
        if not api_key:
            # Webhook-only mode, no scopes to validate
            validated_scopes["connected"] = True
            return validated_scopes

        try:
            url = f"{self.authentication_config.nagios_url}/nagiosxi/api/v1/objects/hoststatus?apikey={api_key}&pretty=1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            validated_scopes["connected"] = True
        except Exception as e:
            validated_scopes["connected"] = str(e)
        return validated_scopes

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts from Nagios XI API if API key is configured.
        """
        api_key = self.authentication_config.api_key
        if not api_key:
            return []

        alerts = []

        # Get service problems
        try:
            url = f"{self.authentication_config.nagios_url}/nagiosxi/api/v1/objects/servicestatus?apikey={api_key}&pretty=1"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            for record in data.get("servicestatus", []):
                status_text = self._nagios_state_to_text(
                    record.get("current_state", "0"), is_host=False
                )
                severity = self.SEVERITIES_MAP.get(status_text, AlertSeverity.INFO)
                status = self.STATUS_MAP.get(status_text, AlertStatus.FIRING)

                last_check = record.get("last_check")
                if last_check:
                    try:
                        last_received = datetime.fromtimestamp(
                            int(last_check), tz=timezone.utc
                        ).isoformat()
                    except (ValueError, TypeError):
                        last_received = datetime.now(tz=timezone.utc).isoformat()
                else:
                    last_received = datetime.now(tz=timezone.utc).isoformat()

                alerts.append(
                    AlertDto(
                        id=f"{record.get('host_name', '')}:{record.get('name', '')}",
                        name=record.get("name", ""),
                        status=status,
                        severity=severity,
                        lastReceived=last_received,
                        source=["nagios"],
                        message=record.get("status_text", ""),
                        host=record.get("host_name", ""),
                        service=record.get("name", ""),
                    )
                )
        except Exception:
            self.logger.exception("Error pulling service alerts from Nagios XI")

        # Get host problems
        try:
            url = f"{self.authentication_config.nagios_url}/nagiosxi/api/v1/objects/hoststatus?apikey={api_key}&pretty=1"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            for record in data.get("hoststatus", []):
                status_text = self._nagios_state_to_text(
                    record.get("current_state", "0"), is_host=True
                )
                severity = self.SEVERITIES_MAP.get(status_text, AlertSeverity.INFO)
                status = self.STATUS_MAP.get(status_text, AlertStatus.FIRING)

                last_check = record.get("last_check")
                if last_check:
                    try:
                        last_received = datetime.fromtimestamp(
                            int(last_check), tz=timezone.utc
                        ).isoformat()
                    except (ValueError, TypeError):
                        last_received = datetime.now(tz=timezone.utc).isoformat()
                else:
                    last_received = datetime.now(tz=timezone.utc).isoformat()

                alerts.append(
                    AlertDto(
                        id=record.get("name", ""),
                        name=f"Host {record.get('name', '')}",
                        status=status,
                        severity=severity,
                        lastReceived=last_received,
                        source=["nagios"],
                        message=record.get("status_text", ""),
                        host=record.get("name", ""),
                        address=record.get("address", ""),
                    )
                )
        except Exception:
            self.logger.exception("Error pulling host alerts from Nagios XI")

        return alerts

    @staticmethod
    def _nagios_state_to_text(state, is_host=False):
        """Convert numeric Nagios state to text."""
        state = int(state) if isinstance(state, str) and state.isdigit() else state
        if is_host:
            return {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}.get(state, "UNKNOWN")
        return {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}.get(
            state, "UNKNOWN"
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook event into an AlertDto.
        """
        host = event.get("host", event.get("host_name", ""))
        service = event.get("service", event.get("service_description", ""))
        status_raw = (
            event.get("status", event.get("host_status", "UNKNOWN")).upper().strip()
        )
        notification_type = (
            event.get("notification_type", "").upper().strip()
        )
        output = event.get("output", event.get("plugin_output", ""))
        long_output = event.get("long_output", event.get("long_plugin_output", ""))
        address = event.get("address", event.get("host_address", ""))

        # Determine if this is a host or service alert
        is_host_alert = not service or status_raw in ("UP", "DOWN", "UNREACHABLE")

        # Set severity
        severity = NagiosProvider.SEVERITIES_MAP.get(status_raw, AlertSeverity.INFO)

        # Determine status from notification type first, then from state
        if notification_type and notification_type in NagiosProvider.NOTIFICATION_TYPE_MAP:
            status = NagiosProvider.NOTIFICATION_TYPE_MAP[notification_type]
        else:
            status = NagiosProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        # Parse event time
        event_time = event.get("event_time", event.get("timet", ""))
        if event_time:
            try:
                last_received = datetime.fromtimestamp(
                    int(event_time), tz=timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                last_received = datetime.now(tz=timezone.utc).isoformat()
        else:
            last_received = datetime.now(tz=timezone.utc).isoformat()

        # Build name
        if service:
            name = f"{service} on {host}"
        else:
            name = f"Host {host}"

        alert = AlertDto(
            id=f"{host}:{service}" if service else host,
            name=name,
            description=output,
            severity=severity,
            status=status,
            host=host,
            service=service if service else None,
            address=address if address else None,
            source=["nagios"],
            output=output,
            long_output=long_output if long_output else None,
            notification_type=notification_type if notification_type else None,
            contact_name=event.get("contact_name"),
            contact_email=event.get("contact_email"),
            attempt=event.get("attempt"),
            max_attempts=event.get("max_attempts"),
            lastReceived=last_received,
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
