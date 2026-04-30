"""
LumigoProvider is a class that provides a way to receive alerts from Lumigo
via webhooks. Lumigo is a serverless observability platform for debugging and
monitoring AWS Lambda and other cloud-native applications.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class LumigoProvider(BaseProvider):
    """Get alerts from Lumigo into Keep via webhooks."""

    PROVIDER_DISPLAY_NAME = "Lumigo"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on setting up Lumigo alerts, refer to the [Lumigo documentation](https://docs.lumigo.io/docs/alerts).

### Connecting Lumigo to Keep

1. Log in to your [Lumigo dashboard](https://platform.lumigo.io).
2. Navigate to **Settings** → **Alerts**.
3. Click **Add Alert Channel** and select **Webhook**.
4. Set the **Webhook URL** to: `{keep_webhook_api_url}`
5. Add a custom HTTP header:
   - **Header name**: `X-API-KEY`
   - **Header value**: `{api_key}`
6. Save the alert channel and configure which alerts should be sent to Keep.
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.MEDIUM,
        "low": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "TRIGGERED": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No authentication required for webhook-only provider."""
        pass

    def dispose(self):
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Lumigo webhook alert payload into a Keep AlertDto.

        Lumigo webhook payload example:
        {
          "id": "alert-123",
          "name": "High Error Rate",
          "description": "Error rate exceeded threshold",
          "status": "TRIGGERED",
          "severity": "high",
          "service": "my-lambda-function",
          "region": "us-east-1",
          "timestamp": "2024-01-01T00:00:00Z",
          "url": "https://platform.lumigo.io/..."
        }
        """
        status_raw = event.get("status", "TRIGGERED")
        status = LumigoProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        severity_raw = event.get("severity", "medium")
        severity = LumigoProvider.SEVERITIES_MAP.get(
            severity_raw.lower() if isinstance(severity_raw, str) else "medium",
            AlertSeverity.MEDIUM,
        )

        alert_id = event.get("id") or event.get("alertId") or event.get("alert_id")
        name = event.get("name") or event.get("alertName") or event.get("alert_name", "Lumigo Alert")
        description = event.get("description") or event.get("message", "")
        service = event.get("service") or event.get("functionName") or event.get("function_name", "")
        region = event.get("region", "")
        url = event.get("url") or event.get("dashboardUrl") or event.get("dashboard_url")

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            status=status,
            severity=severity,
            service=service,
            region=region,
            url=url,
            source=["lumigo"],
            lastReceived=event.get("timestamp") or event.get("triggeredAt"),
        )

        alert.fingerprint = LumigoProvider.get_alert_fingerprint(
            alert,
            fingerprint_fields=LumigoProvider.FINGERPRINT_FIELDS,
        )

        return alert


if __name__ == "__main__":
    pass
