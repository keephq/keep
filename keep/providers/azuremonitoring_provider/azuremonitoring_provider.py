"""
PrometheusProvider is a class that provides a way to read data from Prometheus.
"""

import datetime

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class AzuremonitoringProvider(BaseProvider):
    """Get alerts from Azure Monitor into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Azure Monitor to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/azuremonitoring-provider). 💡

To send alerts from Azure Monitor to Keep, Use the following webhook url to configure Azure Monitor send alerts to Keep:

1. In Azure Monitor, create a new Action Group.
2. In the Action Group, add a new action of type "Webhook".
3. In the Webhook action, configure the webhook with the following settings.
- **Name**: keep-azuremonitoring-webhook-integration
- **URL**: {keep_webhook_api_url_with_auth}
4. Save the Action Group.
5. In the Alert Rule, configure the Action Group to use the Action Group created in step 1.
6. Save the Alert Rule.
7. Test the Alert Rule to ensure that the alerts are being sent to Keep.
"""

    # Maps Azure Monitor severity to Keep's format
    SEVERITIES_MAP = {
        "Sev0": AlertSeverity.CRITICAL,
        "Sev1": AlertSeverity.HIGH,
        "Sev2": AlertSeverity.WARNING,
        "Sev3": AlertSeverity.INFO,
        "Sev4": AlertSeverity.LOW,
    }

    # Maps Azure Monitor monitor condition to Keep's format
    STATUS_MAP = {
        "Resolved": AlertStatus.RESOLVED,
        "Fired": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Azure Monitor"
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Prometheus's provider.
        """
        # no config
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        essentials = event.get("data", {}).get("essentials", {})
        alert_context = event.get("data", {}).get("alertContext", {})

        # Extract and format the alert ID
        alert_id = essentials.get("alertId", "").split("/")[-1]

        # Format the severity
        severity = AzuremonitoringProvider.SEVERITIES_MAP.get(
            essentials.get("severity"), AlertSeverity.INFO
        )

        # Format the status
        status = AzuremonitoringProvider.STATUS_MAP.get(
            essentials.get("monitorCondition"), AlertStatus.FIRING
        )

        # Parse and format the timestamp
        event_time = essentials.get("firedDateTime", essentials.get("resolvedDateTime"))
        if event_time:
            event_time = datetime.datetime.fromisoformat(event_time)

        # Extract other essential fields
        resource_ids = essentials.get("alertTargetIDs", [])
        description = essentials.get("description", "")
        subscription = essentials.get("alertId", "").split("/")[2]

        url = f"https://portal.azure.com/#view/Microsoft_Azure_Monitoring_Alerts/AlertDetails.ReactView/alertId~/%2Fsubscriptions%2F{subscription}%2Fproviders%2FMicrosoft.AlertsManagement%2Falerts%2F{alert_id}"
        # Construct the alert object
        alert = AlertDto(
            id=alert_id,
            name=essentials.get("alertRule", ""),
            status=status,
            lastReceived=str(event_time),
            source=["azuremonitoring"],
            description=description,
            groups=resource_ids,
            severity=severity,
            url=url,
            monitor_id=essentials.get("originAlertId", ""),
            alertContext=alert_context,
            essentials=essentials,
            customProperties=event.get("data", {}).get("customProperties", {}),
        )

        # Set fingerprint if applicable
        return alert


if __name__ == "__main__":
    pass
