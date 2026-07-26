"""
Netdata is a cloud-based monitoring tool that provides real-time monitoring of servers, applications, and devices.
"""

from typing import ClassVar

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class NetdataProvider(BaseProvider):
    """Get alerts from Netdata into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
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

    SEVERITIES_MAP: ClassVar[dict[str, str]] = {
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP: ClassVar[dict[str, str]] = {
        "reachable": AlertStatus.RESOLVED,
        "unreachable": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Netdata"
    PROVIDER_TAGS: ClassVar[list[str]] = ["alert"]
    PROVIDER_CATEGORY: ClassVar[list[str]] = ["Monitoring"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Prometheus's provider.
        """
        # no config

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        alert = AlertDto(
            id=event.get("id", None),
            name=event.get("name", None),
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
            alert=event.get("alert", None),
            url=(
                event["alert_url"] or event["url"]
                if "alert_url" in event or "url" in event
                else None
            ),
            chart=event.get("chart", None),
            alert_class=event.get("class", None),
            context=event.get("context", None),
            lastReceived=event.get("date", None),
            duration=event.get("duration", None),
            info=event.get("info", None),
            space=event.get("space", None),
            total_critical=(event.get("total_critical", None)),
            total_warnings=(event.get("total_warnings", None)),
            value=event.get("value", None),
        )

        return alert


if __name__ == "__main__":
    pass
