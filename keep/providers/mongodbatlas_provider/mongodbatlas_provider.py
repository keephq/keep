"""
MongoDB Atlas provider for Keep.

Receives alert webhooks from MongoDB Atlas monitoring. Atlas sends a JSON
POST to a configured webhook URL when monitoring thresholds are triggered.

No external libraries required — this provider only parses JSON payloads.
"""

import logging
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class MongodbatlasProvider(BaseProvider):
    """Receive MongoDB Atlas monitoring alerts via webhooks."""

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"
    PROVIDER_CATEGORY = ["Database", "Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = []
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_markdown = """
1. In the [MongoDB Atlas UI](https://cloud.mongodb.com), navigate to your **Project**.
2. Go to **Project Settings → Integrations → Webhook**.
3. Set the **Webhook URL** to `{keep_webhook_api_url}`.
4. Add a custom HTTP header `X-API-KEY` with your Keep API key.
5. Click **Save**.
6. Atlas will now POST alert payloads to Keep whenever a monitoring alert is triggered or resolved.
"""

    # Map Atlas status values to Keep AlertStatus
    _STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "CLOSED": AlertStatus.RESOLVED,
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
        "TRACKING": AlertStatus.FIRING,
        "CANCELLED": AlertStatus.RESOLVED,
    }

    # Keywords in typeName / eventTypeName → severity
    _CRITICAL_KEYWORDS = {
        "REPLICATION_OPLOG_WINDOW_RUNNING_OUT",
        "PRIMARY_ELECTED",
        "NO_PRIMARY",
        "RS_STATE",
        "MONGOS_IS_MISSING",
        "CLUSTER_MONGOS_IS_MISSING",
    }

    _HIGH_KEYWORDS = {
        "HOST_DOWN",
        "HOST_NOT_ENOUGH_DISK_SPACE",
        "DISK",
        "OUTSIDE_METRIC_THRESHOLD",
        "CONNECTION",
    }

    _WARNING_KEYWORDS = {
        "CREDIT_CARD",
        "BACKUP",
        "CLUSTER_MONGOS",
        "INSIDE_METRIC_THRESHOLD",
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No authentication required — webhook-only provider."""
        pass

    def dispose(self):
        """Nothing to clean up."""
        pass

    @staticmethod
    def _resolve_severity(event: dict) -> AlertSeverity:
        """Determine alert severity from Atlas typeName or eventTypeName."""
        type_name = (event.get("typeName") or "").upper()
        event_type = (event.get("eventTypeName") or "").upper()
        combined = type_name + " " + event_type

        for keyword in MongodbatlasProvider._CRITICAL_KEYWORDS:
            if keyword in combined:
                return AlertSeverity.CRITICAL

        for keyword in MongodbatlasProvider._HIGH_KEYWORDS:
            if keyword in combined:
                return AlertSeverity.HIGH

        for keyword in MongodbatlasProvider._WARNING_KEYWORDS:
            if keyword in combined:
                return AlertSeverity.WARNING

        return AlertSeverity.INFO

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> "AlertDto | list[AlertDto]":
        """
        Parse a MongoDB Atlas alert webhook payload into an AlertDto.

        Atlas webhook fields:
          - id (str): Unique alert ID
          - created (str): ISO-8601 timestamp when the alert was created
          - updated (str): ISO-8601 timestamp of the last update
          - status (str): OPEN | CLOSED | ACKNOWLEDGED | TRACKING | CANCELLED
          - acknowledgingUsername (str): User who acknowledged the alert
          - alertConfigId (str): ID of the alert configuration that triggered
          - clusterName (str): Name of the Atlas cluster
          - currentValue (dict): {number, units} for metric-based alerts
          - eventTypeName (str): Atlas event category (e.g. OUTSIDE_METRIC_THRESHOLD)
          - humanReadable (str): Human-readable alert description
          - metricName (str): Metric name for metric-based alerts
          - typeName (str): Alert type (e.g. HOST, REPLICA_SET, CLUSTER)
        """
        alert_id = event.get("id")
        status_raw = (event.get("status") or "OPEN").upper()
        status = MongodbatlasProvider._STATUS_MAP.get(status_raw, AlertStatus.FIRING)
        severity = MongodbatlasProvider._resolve_severity(event)

        cluster_name = event.get("clusterName", "")
        event_type = event.get("eventTypeName", "")
        metric_name = event.get("metricName", "")
        human_readable = event.get("humanReadable", "")
        type_name = event.get("typeName", "")

        # Build a meaningful alert name
        parts = [p for p in [type_name, event_type, metric_name] if p]
        name = " / ".join(parts) if parts else "MongoDB Atlas Alert"

        description = human_readable or name

        # Include current metric value in description when available
        current_value = event.get("currentValue")
        if current_value and isinstance(current_value, dict):
            val = current_value.get("number")
            units = current_value.get("units", "")
            if val is not None:
                description = f"{description} (current: {val} {units})".strip()

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=["mongodbatlas"],
            cluster=cluster_name,
            alertConfigId=event.get("alertConfigId"),
            eventTypeName=event_type,
            metricName=metric_name,
            typeName=type_name,
            acknowledgingUsername=event.get("acknowledgingUsername"),
            lastReceived=event.get("updated") or event.get("created"),
        )

        return alert


if __name__ == "__main__":
    pass
