"""
Nagios Provider is a class that provides a way to receive alerts from Nagios
using webhooks and to query host/service status via the Nagios REST API.
"""

import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    NagiosProviderAuthConfig holds the authentication configuration for the
    NagiosProvider.

    Supports both Nagios XI (commercial) and Nagios Core (CGI-based) setups.

    For Nagios XI: provide ``host_url`` and ``api_key``.
    For Nagios Core: provide ``host_url``, ``username``, and ``password``.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "hint": "e.g. https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios XI API Key (for Nagios XI only)",
            "sensitive": True,
        },
    )

    username: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios username (for Nagios Core / basic auth)",
            "sensitive": False,
        },
    )

    password: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios password (for Nagios Core / basic auth)",
            "sensitive": True,
        },
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep.

    Supports two integration modes:
    - **Webhook**: Nagios sends notifications to Keep via the event broker
      or external notification commands.
    - **Pull**: Keep polls Nagios XI REST API or Nagios Core CGI JSON API
      to fetch current host and service statuses.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep via webhook:

**Nagios XI:**
1. In Nagios XI, go to **Admin > Notification Methods**.
2. Add a new notification method of type **Webhook**.
3. Set the webhook URL to: `{keep_webhook_api_url}`
4. Add the HTTP header `x-api-key` with your Keep API key.
5. Save and assign this notification method to your hosts/services.

**Nagios Core (custom notification command):**
1. Add the following command to your Nagios configuration:

```
define command {{
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -o /dev/null \\
        -X POST {keep_webhook_api_url} \\
        -H "x-api-key: {api_key}" \\
        -H "Content-Type: application/json" \\
        -d '{{
            "type": "HOST",
            "hostname": "$HOSTNAME$",
            "hoststate": "$HOSTSTATE$",
            "hostoutput": "$HOSTOUTPUT$",
            "notificationtype": "$NOTIFICATIONTYPE$",
            "datetime": "$LONGDATETIME$"
        }}'
}}

define command {{
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -o /dev/null \\
        -X POST {keep_webhook_api_url} \\
        -H "x-api-key: {api_key}" \\
        -H "Content-Type: application/json" \\
        -d '{{
            "type": "SERVICE",
            "hostname": "$HOSTNAME$",
            "servicedesc": "$SERVICEDESC$",
            "servicestate": "$SERVICESTATE$",
            "serviceoutput": "$SERVICEOUTPUT$",
            "notificationtype": "$NOTIFICATIONTYPE$",
            "datetime": "$LONGDATETIME$"
        }}'
}}
```

2. Assign these commands as notification commands for your contacts.
"""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read host and service alerts from Nagios",
        ),
    ]

    # Nagios host/service state codes
    # Host: 0=UP, 1=DOWN, 2=UNREACHABLE
    # Service: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    HOST_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

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

    SERVICE_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
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
        pass

    def validate_config(self):
        """
        Validates required configuration for the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def _is_nagios_xi(self) -> bool:
        """Return True if this instance is configured for Nagios XI (API key auth)."""
        return bool(self.authentication_config.api_key)

    def _get_xi_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
        }

    def _get_xi_params(self, extra: dict | None = None) -> dict:
        params = {"apikey": self.authentication_config.api_key}
        if extra:
            params.update(extra)
        return params

    def _get_basic_auth(self):
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate provider scopes by testing API connectivity.
        """
        self.logger.info("Validating Nagios provider scopes")
        try:
            if self._is_nagios_xi():
                # Nagios XI: query the objects/hoststatus endpoint
                response = requests.get(
                    f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/hoststatus",
                    headers=self._get_xi_headers(),
                    params={**self._get_xi_params(), "count": 1},
                    timeout=10,
                )
            else:
                # Nagios Core: query the CGI status JSON endpoint
                response = requests.get(
                    f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi",
                    params={"query": "hostcount"},
                    auth=self._get_basic_auth(),
                    timeout=10,
                )

            if response.ok:
                return {"read_alerts": True}
            return {
                "read_alerts": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            return {"read_alerts": str(e)}

    def _get_xi_host_alerts(self) -> list[AlertDto]:
        """Fetch host status alerts from Nagios XI REST API."""
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/hoststatus",
                headers=self._get_xi_headers(),
                params=self._get_xi_params(
                    {"current_state.in": "1,2", "formatoptions": "enumerate"}
                ),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            hosts = data.get("hoststatus", [])
            alerts = []
            for host in hosts:
                state = host.get("current_state", 1)
                alerts.append(
                    AlertDto(
                        id=f"nagios-host-{host.get('host_name')}",
                        name=host.get("host_name"),
                        description=host.get("plugin_output", ""),
                        status=self.HOST_STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.HOST_SEVERITY_MAP.get(
                            state, AlertSeverity.CRITICAL
                        ),
                        lastReceived=datetime.datetime.fromtimestamp(
                            int(host.get("last_check", 0))
                        ).isoformat()
                        if host.get("last_check")
                        else None,
                        host=host.get("host_name"),
                        acknowledged=bool(int(host.get("problem_has_been_acknowledged", 0))),
                        check_command=host.get("check_command"),
                        source=["nagios"],
                    )
                )
            return alerts
        except Exception as e:
            self.logger.error("Failed to fetch Nagios XI host alerts: %s", e)
            raise ProviderException(f"Failed to fetch Nagios XI host alerts: {e}") from e

    def _get_xi_service_alerts(self) -> list[AlertDto]:
        """Fetch service status alerts from Nagios XI REST API."""
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/servicestatus",
                headers=self._get_xi_headers(),
                params=self._get_xi_params(
                    {"current_state.in": "1,2,3", "formatoptions": "enumerate"}
                ),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            services = data.get("servicestatus", [])
            alerts = []
            for svc in services:
                state = svc.get("current_state", 2)
                alerts.append(
                    AlertDto(
                        id=f"nagios-service-{svc.get('host_name')}-{svc.get('service_description')}",
                        name=svc.get("service_description"),
                        description=svc.get("plugin_output", ""),
                        status=self.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.SERVICE_SEVERITY_MAP.get(
                            state, AlertSeverity.WARNING
                        ),
                        lastReceived=datetime.datetime.fromtimestamp(
                            int(svc.get("last_check", 0))
                        ).isoformat()
                        if svc.get("last_check")
                        else None,
                        host=svc.get("host_name"),
                        service=svc.get("service_description"),
                        acknowledged=bool(int(svc.get("problem_has_been_acknowledged", 0))),
                        check_command=svc.get("check_command"),
                        source=["nagios"],
                    )
                )
            return alerts
        except Exception as e:
            self.logger.error("Failed to fetch Nagios XI service alerts: %s", e)
            raise ProviderException(
                f"Failed to fetch Nagios XI service alerts: {e}"
            ) from e

    def _get_core_host_alerts(self) -> list[AlertDto]:
        """Fetch host status alerts from Nagios Core CGI JSON API."""
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi",
                params={"query": "hostlist", "hoststatus": "down+unreachable"},
                auth=self._get_basic_auth(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            host_list = data.get("data", {}).get("hostlist", {})
            alerts = []
            for host_name, host in host_list.items():
                state = host.get("status", "DOWN")
                alerts.append(
                    AlertDto(
                        id=f"nagios-host-{host_name}",
                        name=host_name,
                        description=host.get("plugin_output", ""),
                        status=self.HOST_STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.HOST_SEVERITY_MAP.get(
                            state, AlertSeverity.CRITICAL
                        ),
                        lastReceived=host.get("last_check"),
                        host=host_name,
                        acknowledged=host.get("problem_has_been_acknowledged", False),
                        source=["nagios"],
                    )
                )
            return alerts
        except Exception as e:
            self.logger.error("Failed to fetch Nagios Core host alerts: %s", e)
            raise ProviderException(
                f"Failed to fetch Nagios Core host alerts: {e}"
            ) from e

    def _get_core_service_alerts(self) -> list[AlertDto]:
        """Fetch service status alerts from Nagios Core CGI JSON API."""
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi",
                params={
                    "query": "servicelist",
                    "servicestatus": "warning+critical+unknown",
                },
                auth=self._get_basic_auth(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            service_list = data.get("data", {}).get("servicelist", {})
            alerts = []
            for host_name, services in service_list.items():
                for svc_name, svc in services.items():
                    state = svc.get("status", "CRITICAL")
                    alerts.append(
                        AlertDto(
                            id=f"nagios-service-{host_name}-{svc_name}",
                            name=svc_name,
                            description=svc.get("plugin_output", ""),
                            status=self.SERVICE_STATUS_MAP.get(
                                state, AlertStatus.FIRING
                            ),
                            severity=self.SERVICE_SEVERITY_MAP.get(
                                state, AlertSeverity.WARNING
                            ),
                            lastReceived=svc.get("last_check"),
                            host=host_name,
                            service=svc_name,
                            acknowledged=svc.get(
                                "problem_has_been_acknowledged", False
                            ),
                            source=["nagios"],
                        )
                    )
            return alerts
        except Exception as e:
            self.logger.error("Failed to fetch Nagios Core service alerts: %s", e)
            raise ProviderException(
                f"Failed to fetch Nagios Core service alerts: {e}"
            ) from e

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios (host + service status).
        Automatically selects XI or Core API based on authentication config.
        """
        alerts = []

        if self._is_nagios_xi():
            self.logger.info("Fetching alerts from Nagios XI API")
            try:
                alerts.extend(self._get_xi_host_alerts())
            except Exception as e:
                self.logger.error("Error fetching Nagios XI host alerts: %s", e)
            try:
                alerts.extend(self._get_xi_service_alerts())
            except Exception as e:
                self.logger.error("Error fetching Nagios XI service alerts: %s", e)
        else:
            self.logger.info("Fetching alerts from Nagios Core CGI API")
            try:
                alerts.extend(self._get_core_host_alerts())
            except Exception as e:
                self.logger.error("Error fetching Nagios Core host alerts: %s", e)
            try:
                alerts.extend(self._get_core_service_alerts())
            except Exception as e:
                self.logger.error("Error fetching Nagios Core service alerts: %s", e)

        self.logger.info("Collected %d alerts from Nagios", len(alerts))
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook notification payload into a Keep AlertDto.

        Handles both host and service notification payloads as sent by the
        custom notification commands documented in ``webhook_markdown``.
        """
        notification_type = event.get("type", "SERVICE").upper()
        hostname = event.get("hostname", "unknown")

        if notification_type == "HOST":
            host_state = event.get("hoststate", "DOWN").upper()
            output = event.get("hostoutput", "")
            name = hostname
            alert_id = f"nagios-host-{hostname}"
            status = NagiosProvider.HOST_STATUS_MAP.get(host_state, AlertStatus.FIRING)
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(
                host_state, AlertSeverity.CRITICAL
            )
            service = None
        else:
            svc_state = event.get("servicestate", "CRITICAL").upper()
            output = event.get("serviceoutput", "")
            service = event.get("servicedesc", "unknown")
            name = service
            alert_id = f"nagios-service-{hostname}-{service}"
            status = NagiosProvider.SERVICE_STATUS_MAP.get(svc_state, AlertStatus.FIRING)
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(
                svc_state, AlertSeverity.WARNING
            )

        return AlertDto(
            id=alert_id,
            name=name,
            description=output,
            status=status,
            severity=severity,
            lastReceived=event.get("datetime"),
            host=hostname,
            service=service if notification_type != "HOST" else None,
            notification_type=event.get("notificationtype"),
            source=["nagios"],
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Example: Nagios XI
    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": os.environ.get("NAGIOS_HOST_URL"),
            "api_key": os.environ.get("NAGIOS_API_KEY"),
            "username": os.environ.get("NAGIOS_USERNAME"),
            "password": os.environ.get("NAGIOS_PASSWORD"),
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
    alerts = provider._get_alerts()
    for alert in alerts:
        print(alert)
