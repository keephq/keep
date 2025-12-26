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
    Allows User Authentication with Nagios API.

    config params:
    - host_url: Base URL of Nagios instance
    - api_user: Username for API authentication
    - api_password: Password for API authentication
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
    Get alerts from Nagios into Keep primarily via webhooks.

    feat:
    - Fetching alerts from Nagios services & hosts
    - Mapping Nagios states to Keep alert status and severity
    - Formatting alerts according to Keep's alert model
    - Supporting webhook integration for real-time alerts
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """

To send alerts from Nagios to Keep, configure a new notification command:

1. In Nagios, create a new notification command in your commands.cfg
2. Set the webhook URL as: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key (webhook role)
4. Configure notification rules to use this command
5. Example command definition:
```
define command {
    command_name    notify-keep
    command_line    /usr/bin/curl -s -X POST -H "Content-Type: application/json" -H "X-API-KEY: YOUR_API_KEY" -d '{"host_name":"$HOSTNAME$","service_desc":"$SERVICEDESC$","state":"$SERVICESTATE$","output":"$SERVICEOUTPUT$","notification_type":"$NOTIFICATIONTYPE$"}' {keep_webhook_api_url}
}
```
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True

    # Define provider scopes
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Nagios",
        ),
    ]

    # Nagios states Mapping to Keep alert states
    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "PENDING": AlertStatus.PENDING,
    }

    # Mapping Nagios states to Keep alert severities
    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
        "PENDING": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        Affirms all required authentication parameters are present.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate provider scopes by testing API connectivity.
        Attempts to fetch Nagios status to verify credentials.
        """
        self.logger.info("Validating Nagios provider")
        try:
            # Nagios Core doesn't have a standard REST API
            # We try the common CGI endpoint for status
            response = requests.get(
                url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi?query=hostlist",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
                timeout=30,
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info(
                "Scopes Validation is successful", extra={"response": response.json()}
            )

            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": e})
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios via API.

        Returns:
            list[AlertDto]: List of alerts in Keep format
        """
        self.logger.info("Getting alerts from Nagios")

        try:
            # Fetch service problems from Nagios CGI
            response = requests.get(
                url=f"{self.authentication_config.host_url}/nagios/cgi-bin/statusjson.cgi?query=servicelist&servicestatus=warning+critical+unknown",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
                timeout=30,
            )

            if response.status_code != 200:
                response.raise_for_status()

            data = response.json()
            services = data.get("data", {}).get("servicelist", {})
            
            alerts = []
            for host_name, host_services in services.items():
                for service_name, service_data in host_services.items():
                    state = service_data.get("status", "UNKNOWN")
                    alerts.append(
                        AlertDto(
                            id=f"{host_name}_{service_name}",
                            name=service_name,
                            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                            source=["nagios"],
                            hostname=host_name,
                            service_name=service_name,
                        )
                    )
            
            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from Nagios")
            raise Exception(f"Failed to get alerts from Nagios: {str(e)}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Nagios webhook payload into Keep alert format.

        Args:
            event (dict): Raw alert data from Nagios
            provider_instance (BaseProvider, optional): Provider instance

        Returns:
            AlertDto: Formatted alert in Keep format
        """
        # Extract common Nagios notification fields
        host_name = event.get("host_name") or event.get("HOSTNAME") or event.get("hostname", "unknown")
        service_desc = event.get("service_desc") or event.get("SERVICEDESC") or event.get("service_description", "")
        state = event.get("state") or event.get("SERVICESTATE") or event.get("HOSTSTATE", "UNKNOWN")
        output = event.get("output") or event.get("SERVICEOUTPUT") or event.get("HOSTOUTPUT", "")
        notification_type = event.get("notification_type") or event.get("NOTIFICATIONTYPE", "PROBLEM")
        
        # Determine if this is a host or service alert
        is_host_alert = not service_desc or service_desc == ""
        
        alert_id = f"{host_name}_{service_desc}" if service_desc else host_name
        alert_name = service_desc if service_desc else f"Host: {host_name}"

        alert = AlertDto(
            id=alert_id,
            name=alert_name,
            status=NagiosProvider.STATUS_MAP.get(state.upper(), AlertStatus.FIRING),
            severity=NagiosProvider.SEVERITY_MAP.get(state.upper(), AlertSeverity.INFO),
            description=output,
            source=["nagios"],
            hostname=host_name,
            service_name=service_desc if not is_host_alert else None,
            notification_type=notification_type,
            state=state,
            is_host_alert=is_host_alert,
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    nagios_api_user = os.getenv("NAGIOS_API_USER")
    nagios_api_password = os.getenv("NAGIOS_API_PASSWORD")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": "https://nagios.example.com",
            "api_user": nagios_api_user,
            "api_password": nagios_api_password,
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
