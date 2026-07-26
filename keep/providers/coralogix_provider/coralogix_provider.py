"""
Coralogix is a modern observability platform delivers comprehensive visibility into all your logs, metrics, traces and security events with end-to-end monitoring.
"""

import json
from typing import ClassVar

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class CoralogixProvider(BaseProvider):
    """Get alerts from Coralogix into Keep."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
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

    SEVERITIES_MAP: ClassVar[dict[str, str]] = {
        "debug": AlertSeverity.LOW,
        "verbose": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
        "warn": AlertSeverity.WARNING,
        "error": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }

    PRIORTY_TO_SEVERITY_MAP: ClassVar[dict[str, str]] = {
        "P1": AlertSeverity.CRITICAL,
        "P2": AlertSeverity.HIGH,
        "P3": AlertSeverity.WARNING,
        "P4": AlertSeverity.INFO,
        "P5": AlertSeverity.LOW,
    }

    STATUS_MAP: ClassVar[dict[str, str]] = {
        "resolve": AlertStatus.RESOLVED,
        "trigger": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Coralogix"
    PROVIDER_TAGS: ClassVar[list[str]] = ["alert"]
    PROVIDER_CATEGORY: ClassVar[list[str]] = ["Monitoring"]
    FINGERPRINT_FIELDS: ClassVar[list[str]] = ["alertUniqueIdentifier"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Coralogix's provider.
        """
        # no config

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        fields_list = event.get("fields", [])
        fields = {item["key"]: item["value"] for item in fields_list}

        labels = fields.get("text", fields.get("labels", {}))
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except Exception:
                # Do nothing, keep labels as str
                pass

        severity = AlertSeverity.INFO
        if "severityLowercase" in fields:
            severity = CoralogixProvider.SEVERITIES_MAP.get(
                fields.get("severityLowercase", "info")
            )
        elif "priority" in fields:
            severity = CoralogixProvider.PRIORTY_TO_SEVERITY_MAP.get(
                fields.get("priority", "P5")
            )

        alert = AlertDto(
            id=fields.get("alertUniqueIdentifier"),
            alert_id=event.get("alert_id", None),
            name=event.get("name", None),
            description=event.get("description", None),
            status=CoralogixProvider.STATUS_MAP.get(event["alert_action"]),
            severity=severity,
            lastReceived=fields.get("timestampISO"),
            alertUniqueIdentifier=fields.get("alertUniqueIdentifier"),
            uuid=event.get("uuid", None),
            threshold=event.get("threshold", None),
            timewindow=event.get("timewindow", None),
            group_by_labels=fields.get("group_by_labels"),
            alert_url=event.get("alert_url", None),
            log_url=event.get("log_url", None),
            team=fields.get("team"),
            priority=fields.get("priority"),
            computer=fields.get("computer"),
            fields=fields,
            labels=labels if isinstance(labels, dict) else {},
            source=["coralogix"],
        )

        return alert


if __name__ == "__main__":
    pass
