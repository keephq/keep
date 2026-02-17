"""
Nagios Provider is a class that allows to ingest/digest data from Nagios.
"""

import dataclasses
import datetime
import logging

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

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "hint": "Found in Admin > Manage API Keys",
            "sensitive": True,
        },
    )

    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep."""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated",
            mandatory=True,
            documentation_url="https://www.nagios.org/documentation/",
        ),
    ]

    # Nagios host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
    }

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    # Nagios service states to severity mapping
    SERVICE_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
    }

    # Nagios host states to severity mapping
    HOST_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
    }

    # Webhook severity mapping for string values
    SEVERITIES_MAP = {
        "ok": AlertSeverity.INFO,
        "up": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "unknown": AlertSeverity.INFO,
        "down": AlertSeverity.CRITICAL,
        "unreachable": AlertSeverity.HIGH,
    }

    # Webhook status mapping for string values
    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "up": AlertStatus.RESOLVED,
        "warning": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
        "down": AlertStatus.FIRING,
        "unreachable": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
> Setup webhooks to send Nagios alerts to Keep.

To send alerts from Nagios to Keep, you can configure Nagios to send webhook notifications:

1. Create a notification command in Nagios that sends HTTP POST requests to Keep.
2. The Keep webhook URL is: {keep_webhook_api_url}
3. Use the API key: {api_key}
4. Configure a contact and notification rules to use this command.

Example command definition for `commands.cfg`:

```
define command {{
    command_name    notify-keep
    command_line    /usr/bin/curl -s -X POST -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        -d '{{"host_name": "$HOSTNAME$", "host_state": "$HOSTSTATE$", "host_address": "$HOSTADDRESS$", "service_desc": "$SERVICEDESC$", "service_state": "$SERVICESTATE$", "service_output": "$SERVICEOUTPUT$", "long_service_output": "$LONGSERVICEOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$"}}' \\
        {keep_webhook_api_url}
}}
```
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            url = (
                f"{self.authentication_config.host_url}/api/v1/objects/hoststatus"
                f"?apikey={self.authentication_config.api_key}"
                f"&records=1"
            )
            response = requests.get(
                url,
                verify=self.authentication_config.verify,
            )
            if response.ok:
                scopes = {"authenticated": True}
            else:
                scopes = {
                    "authenticated": f"Error validating scopes: {response.status_code} {response.text}"
                }
        except Exception as e:
            scopes = {
                "authenticated": f"Error validating scopes: {e}",
            }

        return scopes

    def __get_host_alerts(self) -> list[AlertDto]:
        """
        Fetch host status from the Nagios XI API and convert to AlertDto objects.

        Uses the Nagios XI Objects API:
        GET /api/v1/objects/hoststatus?apikey=<KEY>

        Returns:
            list[AlertDto]: List of host alerts.
        """
        url = (
            f"{self.authentication_config.host_url}/api/v1/objects/hoststatus"
            f"?apikey={self.authentication_config.api_key}"
        )
        response = requests.get(
            url,
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()

        data = response.json()
        hosts = data.get("hoststatus", [])
        if isinstance(hosts, dict):
            hosts = [hosts]

        alerts = []
        for host in hosts:
            current_state = int(host.get("current_state", 0))
            # Skip hosts that are UP (state 0) unless they have a problem
            status = NagiosProvider.HOST_STATUS_MAP.get(
                current_state, AlertStatus.FIRING
            )
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(
                current_state, AlertSeverity.INFO
            )

            last_check = host.get("last_check")
            last_received = None
            if last_check:
                try:
                    last_received = datetime.datetime.strptime(
                        last_check, "%Y-%m-%d %H:%M:%S"
                    ).isoformat()
                except (ValueError, TypeError):
                    last_received = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()
            else:
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()

            host_name = host.get("name", host.get("host_name", "unknown"))
            alerts.append(
                AlertDto(
                    id=host.get("host_object_id", host_name),
                    name=f"Host {host_name} is {_state_name_host(current_state)}",
                    status=status,
                    severity=severity,
                    lastReceived=last_received,
                    description=host.get("status_text", host.get("output", "")),
                    source=["nagios"],
                    hostname=host_name,
                    service=host_name,
                    ip_address=host.get("address", ""),
                    current_state=current_state,
                    has_been_acknowledged=host.get("problem_has_been_acknowledged", "0"),
                )
            )
        return alerts

    def __get_service_alerts(self) -> list[AlertDto]:
        """
        Fetch service status from the Nagios XI API and convert to AlertDto objects.

        Uses the Nagios XI Objects API:
        GET /api/v1/objects/servicestatus?apikey=<KEY>

        Returns:
            list[AlertDto]: List of service alerts.
        """
        url = (
            f"{self.authentication_config.host_url}/api/v1/objects/servicestatus"
            f"?apikey={self.authentication_config.api_key}"
        )
        response = requests.get(
            url,
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()

        data = response.json()
        services = data.get("servicestatus", [])
        if isinstance(services, dict):
            services = [services]

        alerts = []
        for service in services:
            current_state = int(service.get("current_state", 0))
            status = NagiosProvider.SERVICE_STATUS_MAP.get(
                current_state, AlertStatus.FIRING
            )
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(
                current_state, AlertSeverity.INFO
            )

            # If the problem has been acknowledged, mark it
            if str(service.get("problem_has_been_acknowledged", "0")) == "1":
                status = AlertStatus.ACKNOWLEDGED

            last_check = service.get("last_check")
            last_received = None
            if last_check:
                try:
                    last_received = datetime.datetime.strptime(
                        last_check, "%Y-%m-%d %H:%M:%S"
                    ).isoformat()
                except (ValueError, TypeError):
                    last_received = datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat()
            else:
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()

            host_name = service.get("host_name", "unknown")
            service_name = service.get("name", service.get("service_description", "unknown"))

            alerts.append(
                AlertDto(
                    id=service.get("servicestatus_id", f"{host_name}/{service_name}"),
                    name=f"{service_name} on {host_name} is {_state_name_service(current_state)}",
                    status=status,
                    severity=severity,
                    lastReceived=last_received,
                    description=service.get("status_text", service.get("output", "")),
                    source=["nagios"],
                    hostname=host_name,
                    service=service_name,
                    current_state=current_state,
                    has_been_acknowledged=service.get("problem_has_been_acknowledged", "0"),
                )
            )
        return alerts

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            self.logger.info("Collecting host alerts from Nagios")
            host_alerts = self.__get_host_alerts()
            alerts.extend(host_alerts)
        except Exception as e:
            self.logger.error("Error getting host alerts from Nagios: %s", e)

        try:
            self.logger.info("Collecting service alerts from Nagios")
            service_alerts = self.__get_service_alerts()
            alerts.extend(service_alerts)
        except Exception as e:
            self.logger.error("Error getting service alerts from Nagios: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook event into an AlertDto.

        Nagios webhook payloads typically contain fields such as:
        - host_name, host_state, host_address
        - service_desc, service_state, service_output
        - notification_type, timestamp
        """
        host_name = event.get("host_name", event.get("hostname", "unknown"))
        service_desc = event.get("service_desc", event.get("service_description", ""))
        host_state = event.get("host_state", "").lower()
        service_state = event.get("service_state", "").lower()
        notification_type = event.get("notification_type", "").lower()
        service_output = event.get("service_output", event.get("output", ""))
        long_service_output = event.get("long_service_output", event.get("long_output", ""))
        host_address = event.get("host_address", event.get("address", ""))
        timestamp = event.get("timestamp", "")

        # Determine if this is a service or host notification
        if service_desc:
            state = service_state or host_state
            name = f"{service_desc} on {host_name}"
            description = service_output
        else:
            state = host_state
            name = f"Host {host_name}"
            description = service_output or f"Host is {host_state}"

        # Map status
        if notification_type in ("acknowledgement", "acknowledged"):
            status = AlertStatus.ACKNOWLEDGED
        elif notification_type == "recovery":
            status = AlertStatus.RESOLVED
        else:
            status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Map severity
        severity = NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO)

        # Parse timestamp
        last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if timestamp:
            try:
                ts = int(timestamp)
                last_received = datetime.datetime.fromtimestamp(
                    ts, tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError, OSError):
                pass

        alert_id = event.get("id", f"{host_name}/{service_desc}" if service_desc else host_name)

        return AlertDto(
            id=alert_id,
            name=name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=description,
            long_description=long_service_output,
            source=["nagios"],
            hostname=host_name,
            service=service_desc if service_desc else host_name,
            ip_address=host_address,
            notification_type=notification_type,
            pushed=True,
            **{k: v for k, v in event.items() if k not in (
                "host_name", "hostname", "host_state", "host_address", "address",
                "service_desc", "service_description", "service_state",
                "service_output", "output", "long_service_output", "long_output",
                "notification_type", "timestamp", "id", "name", "status",
                "severity", "lastReceived", "description", "source",
                "ip_address", "pushed",
            )},
        )


def _state_name_host(state: int) -> str:
    """Convert Nagios host state integer to a human-readable name."""
    return {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}.get(state, "UNKNOWN")


def _state_name_service(state: int) -> str:
    """Convert Nagios service state integer to a human-readable name."""
    return {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}.get(state, "UNKNOWN")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    host_url = os.environ.get("NAGIOS_HOST_URL")
    api_key = os.environ.get("NAGIOS_API_KEY")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": host_url,
            "api_key": api_key,
        },
    )

    provider = NagiosProvider(
        context_manager,
        provider_id="nagios",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Got {len(alerts)} alerts")
    for alert in alerts:
        print(f"  - {alert.name}: {alert.status} ({alert.severity})")
