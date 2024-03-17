"""
PrometheusProvider is a class that provides a way to read data from Prometheus.
"""

import datetime
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class GcpmonitoringProvider(BaseProvider):
    """Get alerts from Azure Monitor into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure GCP Monitoring to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/gcpmonitoring-provider). 💡

To send alerts from GCP Monitoring to Keep, Use the following webhook url to configure GCP Monitoring send alerts to Keep:

1. In GCP Monitoring, go to Notification Channels.
2. In the Webhooks section click "ADD NEW".
3. In the Endpoint URL, configure:
- **Endpoint URL**: {keep_webhook_api_url}
- **Display Name**: keep-gcpmonitoring-webhook-integration
4. Click on "Use HTTP Basic Auth"
- **Auth Username**: api_key
- **Auth Password**: {api_key}
5. Click on "Save".
6. Go the the Alert Policy that you want to send to Keep and click on "Edit".
7. Go to "Notifications and name"
8. Click on "Notification Channels" and select the "keep-gcpmonitoring-webhook-integration" that you created in step 3.
9. Click on "SAVE POLICY".
"""

    # https://github.com/hashicorp/terraform-provider-google/blob/main/google/services/monitoring/resource_monitoring_alert_policy.go#L963
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
    }

    STATUS_MAP = {
        "CLOSED": AlertStatus.RESOLVED,
        "OPEN": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "GCP Monitoring"
    FINGERPRINT_FIELDS = ["incident_id"]

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
        event: dict, provider_instance: Optional["GcpmonitoringProvider"]
    ) -> AlertDto:
        incident = event.get("incident", {})
        description = incident.pop("summary", "")
        status = GcpmonitoringProvider.STATUS_MAP.get(
            incident.pop("state", "").upper(), AlertStatus.FIRING
        )
        url = incident.pop("url", "")
        name = incident.pop("documentation", {}).get("subject")
        incident_id = incident.pop("incident_id", "")
        # Get the severity
        if "severity" in incident:
            severity = GcpmonitoringProvider.SEVERITIES_MAP.get(
                incident.pop("severity").upper(), AlertSeverity.INFO
            )
        # In some cases (this is from the terraform provider) the severity is in the policy_user_labels
        else:
            severity = GcpmonitoringProvider.SEVERITIES_MAP.get(
                incident.get("policy_user_labels", {}).get("severity"),
                AlertSeverity.INFO,
            )
        # Parse and format the timestamp
        event_time = incident.get("started_at")
        if event_time:
            event_time = datetime.datetime.fromtimestamp(event_time)
        else:
            event_time = datetime.datetime.utcnow()
            # replace timezone to utc
            event_time = event_time.replace(tzinfo=datetime.timezone.utc)

        # Construct the alert object
        alert = AlertDto(
            id=incident_id,
            name=name,
            status=status,
            lastReceived=str(event_time),
            source=["gcpmonitoring"],
            description=description,
            severity=severity,
            url=url,
            **incident
        )

        # Set fingerprint if applicable
        alert.fingerprint = BaseProvider.get_alert_fingerprint(
            alert, GcpmonitoringProvider.FINGERPRINT_FIELDS
        )
        return alert


if __name__ == "__main__":
    pass
