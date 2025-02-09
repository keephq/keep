"""
Coralogix is a modern observability platform delivers comprehensive visibility into all your logs, metrics, traces and security events with end-to-end monitoring.
"""

import json

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class CoralogixProvider(BaseProvider):
    """Get alerts from Coralogix into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Coralogix to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/coralogix-provider).

To send alerts from Coralogix to Keep, Use the following webhook url to configure Coralogix send alerts to Keep:

1. From the Coralogix toolbar, navigate to Data Flow > Outbound Webhooks.
2. In the Outbound Webhooks section, click Generic Webhook.
3. Click Add New.
4. Enter a webhook name and set the URL to {keep_webhook_api_url}.
5. Select HTTP method (POST).
6. Add a request header with the key "x-api-key" and the value as {api_key}.
7. Edit the body of the messages that will be sent when the webhook is triggered (optional).
8. Save the configuration.
"""

    SEVERITIES_MAP = {
        "debug": AlertSeverity.LOW,
        "verbose": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
        "warn": AlertSeverity.WARNING,
        "error": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "resolve": AlertStatus.RESOLVED,
        "trigger": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Coralogix"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["alertUniqueIdentifier"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Coralogix's provider.
        """
        # no config
        pass

    def get_value_by_key(fields: dict, key: str):
        for item in fields:
            if item["key"] == key:
                return item["value"]
        return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        fields_list = event["fields"] if "fields" in event else []
        fields = {item["key"]: item["value"] for item in fields_list}

        labels = fields.get("text", fields.get("labels"))
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except Exception:
                # Do nothing, keep labels as str
                pass

        alert = AlertDto(
            id=fields.get("alertUniqueIdentifier"),
            alert_id=event["alert_id"] if "alert_id" in event else None,
            name=event["name"] if "name" in event else None,
            description=event["description"] if "description" in event else None,
            status=CoralogixProvider.STATUS_MAP.get(event["alert_action"]),
            severity=CoralogixProvider.SEVERITIES_MAP.get(
                fields.get("severityLowercase", "info")
            ),
            lastReceived=fields.get("timestampISO"),
            alertUniqueIdentifier=fields.get("alertUniqueIdentifier"),
            uuid=event["uuid"] if "uuid" in event else None,
            threshold=event["threshold"] if "threshold" in event else None,
            timewindow=event["timewindow"] if "timewindow" in event else None,
            group_by_labels=fields.get("group_by_labels"),
            alert_url=event["alert_url"] if "alert_url" in event else None,
            log_url=event["log_url"] if "log_url" in event else None,
            team=fields.get("team"),
            priority=fields.get("priority"),
            computer=fields.get("computer"),
            fields=fields,
            labels=labels,
            source=["coralogix"],
        )

        return alert


if __name__ == "__main__":
    pass
