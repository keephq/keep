"""
SNMP Provider is a class that provides a way to receive alerts from SNMP traps/events via webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    Allows User Authentication with SNMP provider via webhook.

    config params:
    - webhook_url: URL of the SNMP manager webhook endpoint
    - api_key: Optional API key for webhook authentication
    """

    webhook_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Manager Webhook URL",
            "hint": "e.g. https://snmp-manager.example.com/webhook",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "API Key for webhook authentication",
            "sensitive": True,
        }
    )


class SnmpProvider(BaseProvider):
    """
    Get alerts from SNMP traps/events into Keep via webhook integration.

    feat:
    - Receiving SNMP trap notifications from SNMP managers (Zabbix, Nagios, etc.)
    - Mapping SNMP trap OIDs and severity to Keep alert status and severity
    - Formatting alerts according to Keep's alert model
    - Supporting webhook integration for real-time alerts
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = "Receive SNMP trap alerts"
    webhook_template = ""
    webhook_markdown = """

To send SNMP traps to Keep, configure your SNMP manager to send webhook notifications:

1. In your SNMP manager (Zabbix, Nagios, etc.), create a webhook notification
2. Set the webhook URL as: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key (webhook role)
4. Configure the webhook to send JSON in the format expected by this provider
5. For detailed setup instructions, see [Keep documentation](https://docs.keephq.dev/providers/documentation/snmp-provider)
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert", "monitoring", "snmp"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "snmp-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from SNMP traps",
        ),
    ]

    # SNMP generic trap types mapped to Keep alert status
    STATUS_MAP = {
        "up": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
        "coldStart": AlertStatus.FIRING,
        "warmStart": AlertStatus.FIRING,
        "linkDown": AlertStatus.FIRING,
        "linkUp": AlertStatus.RESOLVED,
        "authenticationFailure": AlertStatus.WARNING,
        "egpNeighborLoss": AlertStatus.WARNING,
    }

    # SNMP generic trap types mapped to Keep alert severities
    SEVERITY_MAP = {
        "up": AlertSeverity.INFO,
        "down": AlertSeverity.CRITICAL,
        "coldStart": AlertSeverity.INFO,
        "warmStart": AlertSeverity.INFO,
        "linkDown": AlertSeverity.CRITICAL,
        "linkUp": AlertSeverity.INFO,
        "authenticationFailure": AlertSeverity.WARNING,
        "egpNeighborLoss": AlertSeverity.WARNING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        Affirms all required authentication parameters are present.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate provider scopes by testing webhook connectivity.
        Attempts to send a test notification to verify the webhook URL.
        """
        self.logger.info("Validating SNMP provider")
        try:
            headers = {"Content-Type": "application/json"}
            if self.authentication_config.api_key:
                headers["X-API-KEY"] = self.authentication_config.api_key

            response = requests.get(
                url=self.authentication_config.webhook_url,
                headers=headers,
                timeout=10,
            )

            if response.status_code >= 500:
                response.raise_for_status()

            self.logger.info("Scopes Validation is successful")
            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": e})
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from SNMP manager via webhook/API.

        Returns:
            list[AlertDto]: List of alerts in Keep format
        """
        self.logger.info("Getting alerts from SNMP provider")

        try:
            headers = {"Content-Type": "application/json"}
            if self.authentication_config.api_key:
                headers["X-API-KEY"] = self.authentication_config.api_key

            response = requests.get(
                url=self.authentication_config.webhook_url,
                headers=headers,
                timeout=10,
            )

            if response.status_code != 200:
                response.raise_for_status()

            alerts_data = response.json()
            if not isinstance(alerts_data, list):
                alerts_data = [alerts_data]

            return [
                self._parse_snmp_alert(alert) for alert in alerts_data
            ]

        except Exception as e:
            self.logger.exception("Failed to get alerts from SNMP provider")
            raise Exception(f"Failed to get alerts from SNMP provider: {str(e)}")

    def _parse_snmp_alert(self, alert_data: dict) -> AlertDto:
        """
        Parse a raw SNMP alert dict into an AlertDto.

        Args:
            alert_data: Raw alert data from SNMP manager webhook

        Returns:
            AlertDto: Formatted alert in Keep format
        """
        trap_type = alert_data.get("trap_type", "unknown").lower()
        oid = alert_data.get("oid", "")
        hostname = alert_data.get("hostname", alert_data.get("source", "unknown"))
        description = alert_data.get("description", alert_data.get("message", ""))

        return AlertDto(
            id=alert_data.get("id", oid),
            name=alert_data.get("name", f"SNMP trap: {trap_type}"),
            status=self.STATUS_MAP.get(trap_type, AlertStatus.FIRING),
            severity=self.SEVERITY_MAP.get(trap_type, AlertSeverity.INFO),
            timestamp=alert_data.get("timestamp"),
            lastReceived=alert_data.get("lastReceived"),
            description=description,
            source=["snmp"],
            hostname=hostname,
            service_name=alert_data.get("service_name"),
            oid=oid,
            community=alert_data.get("community"),
            specific_trap=alert_data.get("specific_trap"),
            raw_data=alert_data,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format SNMP webhook payload into Keep alert format.

        Args:
            event (dict): Raw alert data from SNMP manager webhook
            provider_instance (BaseProvider, optional): Provider instance

        Returns:
            AlertDto: Formatted alert in Keep format
        """
        if not provider_instance or not isinstance(provider_instance, SnmpProvider):
            provider_instance = SnmpProvider.__new__(SnmpProvider)

        return provider_instance._parse_snmp_alert(event)


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    snmp_webhook_url = os.getenv("SNMP_WEBHOOK_URL")
    snmp_api_key = os.getenv("SNMP_API_KEY")

    config = ProviderConfig(
        description="SNMP Provider",
        authentication={
            "webhook_url": snmp_webhook_url or "https://snmp-manager.example.com/webhook",
            "api_key": snmp_api_key,
        },
    )

    provider = SnmpProvider(context_manager, "snmp", config)
