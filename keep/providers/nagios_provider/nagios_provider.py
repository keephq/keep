"""
Nagios Provider for Keep - receive alerts from Nagios monitoring system via webhooks and API.
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
    Nagios provider authentication configuration.

    Supports both Nagios Core (with JSON CGI) and Nagios XI (with REST API).
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
        default="",
        metadata={
            "required": False,
            "description": "Nagios XI API Key (leave empty for Nagios Core)",
            "sensitive": True,
        },
    )

    username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Username for Nagios Core authentication",
            "sensitive": False,
        },
    )

    password: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Password for Nagios Core authentication",
            "sensitive": True,
        },
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep.

    Supports:
    - Nagios XI via REST API
    - Nagios Core via JSON CGI
    - Webhook integration for real-time alerts
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, you need to configure a notification command:

**For Nagios Core:**

1. Add a new command definition in your Nagios config:
```
define command {{
    command_name    notify_keep
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: $CONTACTPAGER$" \\
        -d '{{ "host": "$HOSTNAME$", "service": "$SERVICEDESC$", "state": "$SERVICESTATE$", "output": "$SERVICEOUTPUT$", "type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$" }}' \\
        {keep_webhook_api_url}
}}
```

2. Create a contact that uses this command and add your Keep API key as the pager field

**For Nagios XI:**

1. Go to Admin > System Extensions > Manage Components
2. Add a webhook notification method
3. Set the URL to: {keep_webhook_api_url}
4. Add header: X-API-KEY with your Keep API key
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "nagios-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Nagios",
        ),
    ]

    # Nagios host/service state mapping
    STATUS_MAP = {
        # Service states
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        # Host states
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        # Notification types
        "RECOVERY": AlertStatus.RESOLVED,
        "PROBLEM": AlertStatus.FIRING,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
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

    def _is_nagios_xi(self) -> bool:
        """Check if the config points to Nagios XI (has API key)."""
        return bool(self.authentication_config.api_key)

    def validate_scopes(self):
        """Validate provider scopes by testing API connectivity."""
        self.logger.info("Validating Nagios provider scopes")
        try:
            if self._is_nagios_xi():
                response = requests.get(
                    url=f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/hoststatus",
                    params={
                        "apikey": self.authentication_config.api_key,
                        "records": 1,
                    },
                    verify=True,
                )
            else:
                response = requests.get(
                    url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi",
                    params={"query": "programstatus"},
                    auth=(
                        self.authentication_config.username,
                        self.authentication_config.password,
                    ),
                    verify=True,
                )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Nagios scopes validation succeeded")
            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception("Failed to validate Nagios scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Get alerts from Nagios via API."""
        self.logger.info("Getting alerts from Nagios")
        alerts = []

        try:
            if self._is_nagios_xi():
                alerts = self._get_alerts_xi()
            else:
                alerts = self._get_alerts_core()
        except Exception as e:
            self.logger.exception("Failed to get alerts from Nagios")
            raise Exception(f"Failed to get alerts from Nagios: {e}")

        return alerts

    def _get_alerts_xi(self) -> list[AlertDto]:
        """Get alerts from Nagios XI via REST API."""
        response = requests.get(
            url=f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/servicestatus",
            params={
                "apikey": self.authentication_config.api_key,
            },
            verify=True,
        )
        response.raise_for_status()
        data = response.json()
        services = data.get("servicestatus", {}).get("service", [])

        if isinstance(services, dict):
            services = [services]

        return [
            AlertDto(
                id=f"{svc.get('host_name')}/{svc.get('name')}",
                name=svc.get("name", "Unknown Service"),
                status=self.STATUS_MAP.get(
                    svc.get("status_text", "UNKNOWN"), AlertStatus.FIRING
                ),
                severity=self.SEVERITY_MAP.get(
                    svc.get("status_text", "UNKNOWN"), AlertSeverity.INFO
                ),
                description=svc.get("status_text_long", ""),
                hostname=svc.get("host_name"),
                service_name=svc.get("name"),
                source=["nagios"],
                lastReceived=svc.get("last_check"),
            )
            for svc in services
        ]

    def _get_alerts_core(self) -> list[AlertDto]:
        """Get alerts from Nagios Core via JSON CGI."""
        response = requests.get(
            url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi",
            params={
                "query": "servicelist",
                "details": "true",
            },
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=True,
        )
        response.raise_for_status()
        data = response.json()
        service_data = data.get("data", {}).get("servicelist", {})

        alerts = []
        for hostname, services in service_data.items():
            for svc_name, svc_info in services.items():
                state_val = svc_info.get("status", 0)
                state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
                state = state_map.get(state_val, "UNKNOWN")

                alerts.append(
                    AlertDto(
                        id=f"{hostname}/{svc_name}",
                        name=svc_name,
                        status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                        description=svc_info.get("plugin_output", ""),
                        hostname=hostname,
                        service_name=svc_name,
                        source=["nagios"],
                        lastReceived=svc_info.get("last_check"),
                    )
                )

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Nagios webhook payload into Keep alert format.
        """
        host = event.get("host", event.get("hostname", "unknown"))
        service = event.get("service", event.get("service_description", ""))
        state = event.get("state", event.get("service_state", "UNKNOWN"))
        output = event.get("output", event.get("service_output", ""))
        notif_type = event.get("type", event.get("notification_type", ""))
        timestamp = event.get("timestamp", event.get("timet", ""))

        # Use notification type for status if available
        status = NagiosProvider.STATUS_MAP.get(
            notif_type,
            NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
        )
        severity = NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.INFO)

        alert_name = f"{service}" if service else f"{host}"
        alert_id = f"{host}/{service}" if service else host

        return AlertDto(
            id=alert_id,
            name=alert_name,
            status=status,
            severity=severity,
            description=output,
            hostname=host,
            service_name=service if service else None,
            source=["nagios"],
            timestamp=timestamp if timestamp else None,
            notification_type=notif_type,
            state=state,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": os.environ.get("NAGIOS_HOST_URL", "https://nagios.example.com"),
            "api_key": os.environ.get("NAGIOS_API_KEY", ""),
            "username": os.environ.get("NAGIOS_USER", "nagiosadmin"),
            "password": os.environ.get("NAGIOS_PASSWORD", ""),
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
