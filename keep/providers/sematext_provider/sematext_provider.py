"""
SematextProvider integrates Sematext Cloud with Keep.

Sematext Cloud is an observability platform providing metrics, logs, events, and
synthetic monitoring. This provider receives alerts from Sematext via its webhook
(Custom Notification Hook) feature.

Sematext webhook documentation:
  https://sematext.com/docs/alerts/alert-notifications/#custom-notification-hooks
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SematextProviderAuthConfig:
    """
    SematextProviderAuthConfig is a no-op auth config.

    Sematext pushes alerts to Keep via webhook — no outbound credentials are
    needed.  Keep only needs to know *which* Sematext app the webhook is coming
    from, which is implicit in the URL path Keep provides.
    """

    # No authentication fields are required for a pure webhook receiver.
    pass


class SematextProvider(BaseProvider):
    """
    Receive alert notifications from Sematext Cloud via webhook.

    Sematext sends a JSON payload to the Keep inbound webhook URL whenever an
    alert rule fires or recovers.  This provider maps those payloads to Keep
    ``AlertDto`` objects.
    """

    PROVIDER_DISPLAY_NAME = "Sematext"
    PROVIDER_TAGS = ["monitoring", "logging", "observability"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    # ------------------------------------------------------------------
    # Webhook configuration shown in Keep UI
    # ------------------------------------------------------------------

    webhook_description = "Receive alert notifications from Sematext Cloud"
    webhook_template = ""
    webhook_markdown = """
To connect Sematext Cloud alerts to Keep:

1. Log in to [Sematext Cloud](https://apps.sematext.com/).
2. Navigate to the **App** you want to monitor (Monitoring, Logs, or Synthetics).
3. Go to **Alert Rules** and open an existing rule or create a new one.
4. In the **Notifications** section, click **Add Notification Hook**.
5. Select **Custom** (webhook) as the notification type.
6. Enter the following URL:

   `{keep_webhook_api_url}`

7. Set the **Method** to `POST` and **Content-Type** to `application/json`.
8. Leave the **Body** empty — Sematext will send its default JSON payload.
9. Click **Save** and then **Save Rule**.

Keep will now receive alert and recovery notifications from this Sematext app.
"""

    # ------------------------------------------------------------------
    # Alert mapping tables
    # ------------------------------------------------------------------

    # Sematext ruleType/priority string → Keep AlertSeverity
    # Sematext uses: CRITICAL, WARNING, INFO (or numeric 5/4/3/2/1)
    SEVERITY_MAP = {
        # String variants (Sematext alert priority field)
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        # Numeric variants (some Sematext plans use 1-5)
        "5": AlertSeverity.CRITICAL,
        "4": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "2": AlertSeverity.INFO,
        "1": AlertSeverity.LOW,
    }

    # Sematext backToNormal flag → Keep AlertStatus
    # When backToNormal is True the alert has recovered.
    # Sematext also uses a "scheduled" type for maintenance windows.
    RULE_TYPE_STATUS_MAP = {
        "ALERT": AlertStatus.FIRING,
        "ANOMALY": AlertStatus.FIRING,
        "HEARTBEAT": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "SCHEDULED": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def dispose(self):
        pass

    def validate_config(self):
        """No credentials to validate for a pure webhook receiver."""
        self.authentication_config = SematextProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Push mode: _format_alert (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "SematextProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a Sematext webhook payload into a Keep ``AlertDto``.

        Sematext webhook JSON structure (representative fields):
        ```json
        {
          "title": "Alert rule name",
          "description": "Human-readable alert description",
          "ruleType": "ALERT",          // ALERT | ANOMALY | HEARTBEAT | RECOVERY
          "priority": "WARNING",         // CRITICAL | WARNING | INFO | …
          "backToNormal": false,
          "threshold": 95.0,
          "metricValue": 97.3,
          "startedAt": "2026-03-29T10:00:00Z",
          "endedAt": null,
          "appName": "My Production App",
          "appType": "Monitoring",
          "alertRuleId": 12345,
          "tags": {"env": "production"},
          "url": "https://apps.sematext.com/ui/alerts/12345"
        }
        ```
        """

        # --- Status ---
        back_to_normal = event.get("backToNormal", False)
        rule_type = (event.get("ruleType") or "ALERT").strip().upper()

        if back_to_normal:
            status = AlertStatus.RESOLVED
        else:
            status = SematextProvider.RULE_TYPE_STATUS_MAP.get(
                rule_type, AlertStatus.FIRING
            )

        # --- Severity ---
        priority_raw = (event.get("priority") or "").strip().lower()
        severity = SematextProvider.SEVERITY_MAP.get(priority_raw, AlertSeverity.INFO)

        # If the alert is a recovery, cap severity at INFO
        if status == AlertStatus.RESOLVED and severity in (
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
            AlertSeverity.WARNING,
        ):
            severity = AlertSeverity.INFO

        # --- Identity ---
        alert_rule_id = str(event.get("alertRuleId", ""))
        started_at = event.get("startedAt", "")
        # Unique id: rule_id + startedAt avoids collisions across repeated firings
        alert_id = (
            f"sematext-{alert_rule_id}-{started_at}"
            if alert_rule_id
            else f"sematext-{started_at}"
        )

        # --- Timestamps ---
        last_received = started_at or datetime.datetime.utcnow().isoformat() + "Z"

        # --- Names / Descriptions ---
        title = event.get("title", "Sematext Alert")
        description = event.get("description", "")

        # Enrich description with metric context if available
        metric_value = event.get("metricValue")
        threshold = event.get("threshold")
        if metric_value is not None and threshold is not None:
            metric_context = f"Value: {metric_value}, Threshold: {threshold}"
            description = (
                f"{description} [{metric_context}]" if description else metric_context
            )

        # --- Source & Labels ---
        app_name = event.get("appName", "")
        app_type = event.get("appType", "")
        alert_url = event.get("url", "")
        tags = event.get("tags") or {}

        labels = {
            "ruleType": rule_type,
            "alertRuleId": alert_rule_id,
            "appName": app_name,
            "appType": app_type,
            "backToNormal": str(back_to_normal),
            "priority": event.get("priority", ""),
        }
        # Merge Sematext tags into labels
        if isinstance(tags, dict):
            labels.update({f"tag_{k}": str(v) for k, v in tags.items()})

        return AlertDto(
            id=alert_id,
            name=title,
            description=description,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["sematext"],
            service=app_name,
            url=alert_url,
            labels=labels,
        )
