"""
Nagios is a widely-used open source monitoring tool for Infrastructure and Application Monitoring.
https://www.nagios.org/
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    NagiosProviderAuthConfig holds authentication information for the Nagios provider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL (e.g. https://nagios.example.com/nagios)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Username",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Password",
            "sensitive": True,
        },
        default=None,
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep.

    Supports both:
    - Pulling alerts via Nagios CGI JSON API (statusjson.cgi)
    - Receiving alerts via webhook (push from Nagios notification commands)
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "service", "name"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to Nagios",
        ),
    ]

    # Nagios host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        0: AlertSeverity.INFO,       # OK / UP
        1: AlertSeverity.WARNING,    # WARNING / DOWN
        2: AlertSeverity.CRITICAL,   # CRITICAL / UNREACHABLE
        3: AlertSeverity.INFO,       # UNKNOWN
        "OK": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "DOWN": AlertSeverity.CRITICAL,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    webhook_description = "Configure Nagios to send alerts to Keep via webhook."
    webhook_template = ""
    webhook_markdown = """
## Nagios Webhook Integration

To configure Nagios to send alerts to Keep:

### 1. Create a notification command

Add the following to your Nagios commands configuration (e.g., `/etc/nagios/objects/commands.cfg`):

```cfg
define command {{
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        -d '{{"host": "$HOSTNAME$", "alias": "$HOSTALIAS$", "address": "$HOSTADDRESS$", "status": "$HOSTSTATE$", "status_type": "$HOSTSTATETYPE$", "output": "$HOSTOUTPUT$", "long_output": "$LONGHOSTOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "last_check": "$LASTHOSTCHECK$", "last_state_change": "$LASTHOSTSTATECHANGE$", "attempt": "$HOSTATTEMPT$", "max_attempts": "$MAXHOSTATTEMPTS$", "downtime_depth": "$HOSTDOWNTIMEDEPTH$", "acknowledged": "$HOSTACKAUTHOR$", "what": "HOST"}}' \\
        "{keep_webhook_api_url}"
}}

define command {{
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: {api_key}" \\
        -d '{{"host": "$HOSTNAME$", "service": "$SERVICEDESC$", "status": "$SERVICESTATE$", "status_type": "$SERVICESTATETYPE$", "output": "$SERVICEOUTPUT$", "long_output": "$LONGSERVICEOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "last_check": "$LASTSERVICECHECK$", "last_state_change": "$LASTSERVICESTATECHANGE$", "attempt": "$SERVICEATTEMPT$", "max_attempts": "$MAXSERVICEATTEMPTS$", "severity": "$SERVICESTATE$", "what": "SERVICE"}}' \\
        "{keep_webhook_api_url}"
}}
```

### 2. Create a contact for Keep

```cfg
define contact {{
    contact_name                    keep
    alias                           Keep Alert Manager
    service_notification_period     24x7
    host_notification_period        24x7
    service_notification_options    w,u,c,r
    host_notification_options       d,u,r
    service_notification_commands   notify-keep-service
    host_notification_commands      notify-keep-host
}}
```

### 3. Add the contact to your contact group

```cfg
define contactgroup {{
    contactgroup_name   admins
    alias               Nagios Administrators
    members             nagiosadmin,keep
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
        Validates the configuration of the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the Nagios provider by making a test request.
        """
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/cgi-bin/statusjson.cgi?query=hostcount",
                auth=(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                timeout=10,
                verify=False,
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
        Fetch host alerts from Nagios CGI JSON API.
        """
        try:
            url = (
                f"{self.authentication_config.host_url}/cgi-bin/statusjson.cgi"
                "?query=hostlist&details=true"
            )
            response = requests.get(
                url,
                auth=(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                timeout=30,
                verify=False,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get host status from Nagios: %s %s",
                    response.status_code,
                    response.text,
                )
                raise ProviderException("Failed to get host status from Nagios")

            data = response.json()
            host_list = data.get("data", {}).get("hostlist", {})

            alerts = []
            for host_name, host_data in host_list.items():
                status_code = host_data.get("status", 0)
                last_check = host_data.get("last_check", 0)

                alerts.append(
                    AlertDto(
                        id=f"nagios-host-{host_name}",
                        name=host_name,
                        host=host_name,
                        description=host_data.get("plugin_output", ""),
                        status=self.HOST_STATUS_MAP.get(
                            status_code, AlertStatus.FIRING
                        ),
                        severity=self.SEVERITY_MAP.get(
                            status_code, AlertSeverity.INFO
                        ),
                        acknowledged=host_data.get(
                            "problem_has_been_acknowledged", False
                        ),
                        lastReceived=(
                            datetime.datetime.fromtimestamp(last_check).isoformat()
                            if last_check
                            else datetime.datetime.now().isoformat()
                        ),
                        source=["nagios"],
                        what="HOST",
                        address=host_data.get("host_address", ""),
                        max_check_attempts=host_data.get("max_attempts", 0),
                        current_attempt=host_data.get("current_attempt", 0),
                        downtime_depth=host_data.get("scheduled_downtime_depth", 0),
                    )
                )

            return alerts

        except ProviderException:
            raise
        except Exception as e:
            self.logger.error("Error getting host alerts from Nagios: %s", e)
            raise ProviderException(
                f"Error getting host alerts from Nagios: {e}"
            ) from e

    def __get_service_alerts(self) -> list[AlertDto]:
        """
        Fetch service alerts from Nagios CGI JSON API.
        """
        try:
            url = (
                f"{self.authentication_config.host_url}/cgi-bin/statusjson.cgi"
                "?query=servicelist&details=true"
            )
            response = requests.get(
                url,
                auth=(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                timeout=30,
                verify=False,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get service status from Nagios: %s %s",
                    response.status_code,
                    response.text,
                )
                raise ProviderException("Failed to get service status from Nagios")

            data = response.json()
            service_list = data.get("data", {}).get("servicelist", {})

            alerts = []
            for host_name, services in service_list.items():
                for service_name, service_data in services.items():
                    status_code = service_data.get("status", 0)
                    last_check = service_data.get("last_check", 0)

                    alerts.append(
                        AlertDto(
                            id=f"nagios-svc-{host_name}-{service_name}",
                            name=service_name,
                            host=host_name,
                            service=service_name,
                            description=service_data.get("plugin_output", ""),
                            status=self.SERVICE_STATUS_MAP.get(
                                status_code, AlertStatus.FIRING
                            ),
                            severity=self.SEVERITY_MAP.get(
                                status_code, AlertSeverity.INFO
                            ),
                            acknowledged=service_data.get(
                                "problem_has_been_acknowledged", False
                            ),
                            lastReceived=(
                                datetime.datetime.fromtimestamp(
                                    last_check
                                ).isoformat()
                                if last_check
                                else datetime.datetime.now().isoformat()
                            ),
                            source=["nagios"],
                            what="SERVICE",
                            max_check_attempts=service_data.get("max_attempts", 0),
                            current_attempt=service_data.get("current_attempt", 0),
                            downtime_depth=service_data.get(
                                "scheduled_downtime_depth", 0
                            ),
                        )
                    )

            return alerts

        except ProviderException:
            raise
        except Exception as e:
            self.logger.error("Error getting service alerts from Nagios: %s", e)
            raise ProviderException(
                f"Error getting service alerts from Nagios: {e}"
            ) from e

    def _get_alerts(self) -> list[AlertDto]:
        """
        Collect all alerts from Nagios (hosts + services).
        """
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
        event: dict, provider_instance: "NagiosProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook event into an AlertDto.
        This handles incoming webhook notifications from Nagios notification commands.
        """
        host = event.get("host", "unknown")
        service = event.get("service")
        status = event.get("status", "UNKNOWN")
        what = event.get("what", "SERVICE" if service else "HOST")
        notification_type = event.get("notification_type", "")

        # Determine status mapping
        if what == "HOST":
            alert_status = NagiosProvider.HOST_STATUS_MAP.get(
                status, AlertStatus.FIRING
            )
        else:
            alert_status = NagiosProvider.SERVICE_STATUS_MAP.get(
                status, AlertStatus.FIRING
            )

        # Handle acknowledgements
        if notification_type == "ACKNOWLEDGEMENT":
            alert_status = AlertStatus.ACKNOWLEDGED

        severity = NagiosProvider.SEVERITY_MAP.get(status, AlertSeverity.INFO)

        # Parse timestamps
        last_check = event.get("last_check")
        last_state_change = event.get("last_state_change")
        last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if last_check:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(last_check), tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                pass

        alert_id = f"nagios-{host}"
        name = host
        if service:
            alert_id = f"nagios-{host}-{service}"
            name = f"{service} on {host}"

        return AlertDto(
            id=alert_id,
            name=name,
            host=host,
            service=service,
            description=event.get("output", ""),
            long_output=event.get("long_output", ""),
            status=alert_status,
            severity=severity,
            acknowledged=bool(event.get("acknowledged")),
            notification_type=notification_type,
            lastReceived=last_received,
            last_state_change=last_state_change,
            source=["nagios"],
            what=what,
            status_type=event.get("status_type"),
            current_attempt=event.get("attempt"),
            max_check_attempts=event.get("max_attempts"),
            downtime_depth=event.get("downtime_depth"),
            address=event.get("address"),
            alias=event.get("alias"),
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.environ.get("NAGIOS_HOST_URL")
    username = os.environ.get("NAGIOS_USERNAME")
    password = os.environ.get("NAGIOS_PASSWORD")

    if host_url is None:
        raise ProviderException("NAGIOS_HOST_URL is not set")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": host_url,
            "username": username,
            "password": password,
        },
    )

    provider = NagiosProvider(
        context_manager,
        provider_id="nagios",
        config=config,
    )

    alerts = provider._get_alerts()
    for alert in alerts:
        print(alert)
