"""
Icinga2 Provider is a class that provides a way to receive alerts from Icinga2 using webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class Icinga2ProviderAuthConfig:
    """
    Allows User Authentication with Icinga2 API.

    config params:
    - host_url: Base URL of Icinga2 instance
    - api_user: Username for API authentication
    - api_password: Password for API authentication
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Icinga2 Host URL",
            "hint": "e.g. https://icinga2.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_user: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Icinga2 API User",
            "sensitive": False,
        }
    )

    api_password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Icinga2 API Password",
            "sensitive": True,
        }
    )


class Icinga2Provider(BaseProvider):
    """
    Get alerts from Icinga2 into Keep primarily via webhooks.

    feat:
    - Fetching alerts from Icinga2 services & hosts
    - Mapping Icinga2 states to Keep alert status and severity
    - Formatting alerts according to Keep's alert model
    - Supporting webhook integration for real-time alerts
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """

To send alerts from Icinga2 to Keep, configure a new notification command:

1. In Icinga2, create a new notification command
2. Set the webhook URL as: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key (webhook role)
4. Configure notification rules to use this command
5. For detailed setup instructions, see [Keep documentation](https://docs.keephq.dev/providers/documentation/icinga2-provider)
    """

    PROVIDER_DISPLAY_NAME = "Icinga2"
    PROVIDER_TAGS = ["alert", "monitoring"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "icinga2-icon.png"

    # Define provider scopes
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Icinga2",
        ),
    ]

    # Icinga2 states Mapping to Keep alert states ...
    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
    }

    # Mapping Icinga2 states to Keep alert severities
    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Icinga2 provider.
        Affirms all required authentication parameters are present.
        """
        self.authentication_config = Icinga2ProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate provider scopes by testing API connectivity.
        Attempts to fetch Icinga2 status to verify credentials.
        """
        self.logger.info("Validating Icinga2 provider")
        try:
            response = requests.get(
                url=f"{self.authentication_config.host_url}/v1/status",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
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
        Get alerts from Icinga2 via API.

        Returns:
            list[AlertDto]: List of alerts in Keep format
        """
        self.logger.info("Getting alerts from Icinga2")

        try:
            response = requests.get(
                url=f"{self.authentication_config.host_url}/v1/services?attrs=name,display_name,state,last_state_change",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
            )

            if response.status_code != 200:
                response.raise_for_status()

            services = response.json()["results"]

            return [
                AlertDto(
                    id=service.get("name"),
                    name=service.get("display_name"),
                    status=self.STATUS_MAP.get(
                        service.get("state"), AlertStatus.FIRING
                    ),
                    severity=self.SEVERITY_MAP.get(
                        service.get("state"), AlertSeverity.INFO
                    ),
                    timestamp=service.get("last_state_change"),
                    source=["icinga2"],
                )
                for service in services
            ]

        except Exception as e:
            self.logger.exception("Failed to get alerts from Icinga2")
            raise Exception(f"Failed to get alerts from Icinga2: {str(e)}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Icinga2 webhook payload into Keep alert format.

        Args:
            event (dict): Raw alert data from Icinga2
            provider_instance (BaseProvider, optional): Provider instance

        Returns:
            AlertDto: Formatted alert in Keep format
        """
        check_result = event.get("check_result", {})
        service = event.get("service", {})
        host = event.get("host", {})

        status = check_result.get("exit_status", 0)
        state = check_result.get("state", "UNKNOWN")
        output = check_result.get("output", "No output provided")

        alert = AlertDto(
            id=service.get("name") or host.get("name"),
            name=service.get("display_name") or host.get("display_name"),
            status=Icinga2Provider.STATUS_MAP.get(state, AlertStatus.FIRING),
            severity=Icinga2Provider.SEVERITY_MAP.get(state, AlertSeverity.INFO),
            timestamp=check_result.get("execution_start"),
            lastReceived=check_result.get("execution_end"),
            description=output,
            source=["icinga2"],
            hostname=host.get("name"),
            service_name=service.get("name"),
            check_command=service.get("check_command") or host.get("check_command"),
            state=state,
            state_type=check_result.get("state_type"),
            attempt=check_result.get("attempt"),
            acknowledgement=service.get("acknowledgement")
            or host.get("acknowledgement"),
            downtime_depth=service.get("downtime_depth") or host.get("downtime_depth"),
            flapping=service.get("flapping") or host.get("flapping"),
            execution_time=check_result.get("execution_time"),
            latency=check_result.get("latency"),
            raw_output=output,
            exit_status=status,
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

    icinga2_api_user = os.getenv("ICINGA2_API_USER")
    icinga2_api_password = os.getenv("ICINGA2_API_PASSWORD")

    config = ProviderConfig(
        description="Icinga2 Provider",
        authentication={
            "host_url": "https://icinga2.example.com",
            "api_user": icinga2_api_user,
            "api_password": icinga2_api_password,
        },
    )

    provider = Icinga2Provider(context_manager, "icinga2", config)
