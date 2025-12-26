"""
Nagios Provider is a class that provides a way to receive alerts from Nagios using webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios API authentication config.

    Args:
        host_url: Nagios server URL
        api_user: API username
        api_password: API password
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

    api_user: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API User",
            "sensitive": False,
        }
    )

    api_password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API Password",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep via webhooks.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """

To send alerts from Nagios to Keep, configure a notification command:

1. Add a command to commands.cfg:
```
define command {
    command_name    notify-keep
    command_line    /usr/bin/curl -s -X POST -H "Content-Type: application/json" -H "X-API-KEY: YOUR_API_KEY" -d '{"host_name":"$HOSTNAME$","service_desc":"$SERVICEDESC$","state":"$SERVICESTATE$","output":"$SERVICEOUTPUT$"}' {keep_webhook_api_url}
}
```
2. Use this command in your notification definitions
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Nagios",
        ),
    ]

    # Nagios state -> Keep status
    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        self.logger.info("Validating Nagios provider scopes")
        try:
            # nagios core uses CGI for json api
            resp = requests.get(
                url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi?query=hostlist",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
                timeout=30,
            )

            if resp.status_code != 200:
                resp.raise_for_status()

            self.logger.info("Scopes validation successful")
            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Fetching alerts from Nagios")

        try:
            resp = requests.get(
                url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi?query=servicelist&servicestatus=warning+critical+unknown",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
                timeout=30,
            )
            resp.raise_for_status()

            data = resp.json()
            servicelist = data.get("data", {}).get("servicelist", {})

            alerts = []
            for hostname, svcs in servicelist.items():
                for svc_name, svc_data in svcs.items():
                    state = svc_data.get("status", "UNKNOWN")
                    alerts.append(
                        AlertDto(
                            id=f"{hostname}_{svc_name}",
                            name=svc_name,
                            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                            source=["nagios"],
                            hostname=hostname,
                            service_name=svc_name,
                        )
                    )

            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from Nagios")
            raise Exception(f"Failed to get alerts: {e}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        # try different field names that nagios might send
        host = event.get("host_name") or event.get("HOSTNAME", "unknown")
        svc = event.get("service_desc") or event.get("SERVICEDESC", "")
        state = event.get("state") or event.get("SERVICESTATE") or event.get("HOSTSTATE", "UNKNOWN")
        output = event.get("output") or event.get("SERVICEOUTPUT") or event.get("HOSTOUTPUT", "")

        # host alert if no service
        is_host = not svc

        return AlertDto(
            id=f"{host}_{svc}" if svc else host,
            name=svc if svc else f"Host: {host}",
            status=NagiosProvider.STATUS_MAP.get(state.upper(), AlertStatus.FIRING),
            severity=NagiosProvider.SEVERITY_MAP.get(state.upper(), AlertSeverity.INFO),
            description=output,
            source=["nagios"],
            hostname=host,
            service_name=svc if not is_host else None,
            state=state,
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": os.environ.get("NAGIOS_HOST", "https://nagios.example.com"),
            "api_user": os.environ.get("NAGIOS_USER"),
            "api_password": os.environ.get("NAGIOS_PASS"),
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
