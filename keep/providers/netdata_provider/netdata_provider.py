"""
Netdata is a cloud-based monitoring tool that provides real-time monitoring of servers, applications, and devices.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class NetdataProvider(BaseProvider):
    """Get alerts from Netdata into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Netdata to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/netdata-provider).

To send alerts from Netdata to Keep, Use the following webhook url to configure Netdata send alerts to Keep:

1. In Netdata, go to Space settings.
2. Go to "Alerts & Notifications".
3. Click on "Add configuration".
4. Add "Webhook" as the notification method.
5. Add a name to the configuration.
6. Select Room(s) to apply the configuration.
7. Select Notification(s) to apply the configuration.
8. In the "Webhook URL" field, add {keep_webhook_api_url}.
9. Add a request header with the key "x-api-key" and the value as {api_key}.
10. Leave the Authentication as "No Authentication".
11. Add the "Challenge secret" as "keep-netdata-webhook-integration".
12. Save the configuration.
"""

    SEVERITIES_MAP = {
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "reachable": AlertStatus.RESOLVED,
        "unreachable": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Netdata"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

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
        alert = AlertDto(
            id=event["id"] if "id" in event else None,
            name=event["name"] if "name" in event else None,
            host=event["host"],
            message=event["message"],
            severity=NetdataProvider.SEVERITIES_MAP.get(
                event["severity"], AlertSeverity.INFO
            ),
            status=(
                NetdataProvider.STATUS_MAP.get(
                    event["status"]["text"], AlertStatus.FIRING
                )
                if "status" in event
                else AlertStatus.FIRING
            ),
            alert=event["alert"] if "alert" in event else None,
            url=(
                event["alert_url"] or event["url"]
                if "alert_url" in event or "url" in event
                else None
            ),
            chart=event["chart"] if "chart" in event else None,
            alert_class=event["class"] if "class" in event else None,
            context=event["context"] if "context" in event else None,
            lastReceived=event["date"] if "date" in event else None,
            duration=event["duration"] if "duration" in event else None,
            info=event["info"] if "info" in event else None,
            space=event["space"] if "space" in event else None,
            total_critical=(
                event["total_critical"] if "total_critical" in event else None
            ),
            total_warnings=(
                event["total_warnings"] if "total_warnings" in event else None
            ),
            value=event["value"] if "value" in event else None,
        )

        return alert


if __name__ == "__main__":
    pass
