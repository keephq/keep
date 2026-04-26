"""
AppSignalProvider is a class that provides a way to receive alerts from AppSignal
via webhooks. AppSignal is an application performance monitoring (APM) and error
tracking platform for Ruby, Elixir, Node.js, and other languages.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class AppsignalProvider(BaseProvider):
    """Get alerts from AppSignal into Keep via webhooks."""

    PROVIDER_DISPLAY_NAME = "AppSignal"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Application Performance"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on AppSignal notifications, refer to the [AppSignal documentation](https://docs.appsignal.com/application/integrations/webhooks.html).

### Connecting AppSignal to Keep

1. Log in to your [AppSignal dashboard](https://appsignal.com).
2. Go to your application and navigate to **App Settings** → **Notifications** → **Webhooks**.
3. Click **Add webhook**.
4. Set the **Webhook URL** to: `{keep_webhook_api_url}`
5. Add a custom header:
   - **Header name**: `X-API-KEY`
   - **Header value**: `{api_key}`
6. Select the notification events you want to forward to Keep (e.g., errors, performance issues, uptime checks).
7. Click **Save** to activate the webhook.
"""

    SEVERITIES_MAP = {
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.MEDIUM,
        "notice": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "opened": AlertStatus.FIRING,
        "closed": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
        "firing": AlertStatus.FIRING,
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
        Format an AppSignal webhook payload into a Keep AlertDto.

        AppSignal webhook payload structure varies by event type. Common examples:

        Error incident:
        {
          "exception": {
            "id": "abc123",
            "action": "UsersController#show",
            "exception": "NoMethodError",
            "message": "undefined method 'foo' for nil:NilClass",
            "url": "https://appsignal.com/...",
            "status": "opened"
          }
        }

        Performance incident:
        {
          "performance": {
            "id": "def456",
            "action": "UsersController#index",
            "duration": 5000,
            "url": "https://appsignal.com/...",
            "status": "opened"
          }
        }
        """
        # AppSignal wraps the payload in a type key (exception, performance, etc.)
        incident = None
        incident_type = "unknown"

        for key in ("exception", "performance", "host", "uptime", "anomaly"):
            if key in event:
                incident = event[key]
                incident_type = key
                break

        if incident is None:
            incident = event

        alert_id = str(incident.get("id", ""))
        status_raw = incident.get("status", "opened")
        status = AppsignalProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        # Derive name and description based on incident type
        if incident_type == "exception":
            name = incident.get("exception") or "AppSignal Exception"
            description = incident.get("message") or ""
            severity = AlertSeverity.HIGH
        elif incident_type == "performance":
            name = f"Slow transaction: {incident.get('action', '')}"
            description = f"Duration: {incident.get('duration', '')}ms"
            severity = AlertSeverity.MEDIUM
        elif incident_type == "host":
            name = incident.get("name") or "AppSignal Host Alert"
            description = incident.get("description", "")
            severity = AlertSeverity.HIGH
        elif incident_type == "uptime":
            name = incident.get("name") or "AppSignal Uptime Alert"
            description = incident.get("description", "")
            severity = AlertSeverity.CRITICAL
        else:
            name = incident.get("name") or incident.get("exception") or "AppSignal Alert"
            description = incident.get("message") or incident.get("description", "")
            severity = AppsignalProvider.SEVERITIES_MAP.get(
                incident.get("severity", "error"), AlertSeverity.MEDIUM
            )

        url = incident.get("url") or incident.get("dashboard_url")

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            status=status,
            severity=severity,
            incident_type=incident_type,
            action=incident.get("action"),
            url=url,
            source=["appsignal"],
        )

        alert.fingerprint = AppsignalProvider.get_alert_fingerprint(
            alert,
            fingerprint_fields=AppsignalProvider.FINGERPRINT_FIELDS,
        )

        return alert


if __name__ == "__main__":
    pass
