"""
Sematext Cloud provider for Keep.

Sematext Cloud is an all-in-one observability platform for metrics, logs,
events, and synthetic monitoring.  This provider receives alerts via
Sematext's Custom Notification Hook (webhook) — no API credentials are
needed on the Keep side.

Docs: https://sematext.com/docs/integration/alerts-webhooks-integration/
"""

import hashlib
import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Sematext ruleType values and their descriptions:
#   HEARTBEAT            – host/service heartbeat failure
#   AF_VALUE             – infrastructure metric threshold
#   AF_ANOMALY_VALUE     – infrastructure metric anomaly
#   LOGSENE_VALUE        – log-based metric threshold
#   LOGSENE_ANOMALY_VALUE – log-based metric anomaly
#   RUM_VALUE            – real-user monitoring threshold
#   RUM_ANOMALY_VALUE    – RUM anomaly
#   SYNTHETICS_RESULT_VALUE – synthetic monitor result

# Rule types that indicate an anomaly-based alert
_ANOMALY_RULE_TYPES = frozenset(
    {"AF_ANOMALY_VALUE", "LOGSENE_ANOMALY_VALUE", "RUM_ANOMALY_VALUE"}
)

# Severity mapping: Sematext uses the "priority" field when present.
# Values can be strings or ints (1-5).
_SEVERITY_MAP = {
    "CRITICAL": AlertSeverity.CRITICAL,
    "ERROR": AlertSeverity.HIGH,
    "WARNING": AlertSeverity.WARNING,
    "INFO": AlertSeverity.INFO,
    "LOW": AlertSeverity.LOW,
    5: AlertSeverity.CRITICAL,
    4: AlertSeverity.HIGH,
    3: AlertSeverity.WARNING,
    2: AlertSeverity.INFO,
    1: AlertSeverity.LOW,
}


class SematextProvider(BaseProvider):
    """Receive alerts from Sematext Cloud via webhook."""

    PROVIDER_DISPLAY_NAME = "Sematext"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Connect Sematext Cloud to Keep

1. In Sematext, go to **Alerts → Notification Hooks** and click **New Notification Hook**.
2. Select the **Custom** webhook type.
3. Configure the hook:
   - **Name**: `Keep`
   - **URL**: `{keep_webhook_api_url}`
   - **HTTP Method**: `POST`
   - **Send data as**: `JSON`
4. Add a custom header:
   - **Name**: `X-API-KEY`
   - **Value**: `{api_key}`
5. In the **Parameters** section, paste the following JSON body:

```json
{{
  "backToNormal": "$backToNormal",
  "ruleType": "$ruleType",
  "description": "$description",
  "title": "$title",
  "applicationId": "$applicationId",
  "url": "$url",
  "createTimestamp": "$createTimestamp",
  "troubleshootUrl": "$troubleshootUrl"
}}
```

6. Click **Test** to verify, then **Save Notification Hook**.
7. Attach the hook to your alert rules via **Notifications → Send to**.

When alerts fire (or resolve), Sematext will POST to Keep automatically.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No authentication configuration is required — this is a webhook-only
        provider.
        """
        pass

    def dispose(self):
        pass

    # ------------------------------------------------------------------
    # Webhook payload → AlertDto
    # ------------------------------------------------------------------
    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        back_to_normal = _is_back_to_normal(event)
        rule_type = event.get("ruleType", "")

        # ---- status -------------------------------------------------
        if back_to_normal:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        # ---- severity -----------------------------------------------
        severity = _derive_severity(event, back_to_normal)

        # ---- name / description -------------------------------------
        title = event.get("title") or "Sematext Alert"
        description = event.get("description", "")

        # ---- id (fingerprint seed) -----------------------------------
        alert_id = _build_alert_id(event)

        # ---- lastReceived -------------------------------------------
        last_received = event.get("createTimestamp") or (
            datetime.now(timezone.utc).isoformat()
        )

        # ---- url ----------------------------------------------------
        url = event.get("troubleshootUrl") or event.get("url") or None

        # ---- labels -------------------------------------------------
        labels = _build_labels(event)

        return AlertDto(
            id=alert_id,
            name=title,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=description,
            url=url,
            source=["sematext"],
            labels=labels,
        )


# ------------------------------------------------------------------
# Helpers (module-private)
# ------------------------------------------------------------------

def _is_back_to_normal(event: dict) -> bool:
    """Determine whether the event represents a recovery."""
    val = event.get("backToNormal")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return False


def _derive_severity(event: dict, back_to_normal: bool) -> AlertSeverity:
    """Map Sematext priority / ruleType to Keep severity."""
    # If the event carries a priority field, use it.
    priority = event.get("priority")
    if priority is not None:
        # Try case-insensitive string match first, then int.
        if isinstance(priority, str):
            sev = _SEVERITY_MAP.get(priority.upper())
            if sev:
                return sev
            # Might be a numeric string
            try:
                sev = _SEVERITY_MAP.get(int(priority))
                if sev:
                    return sev
            except (ValueError, TypeError):
                pass
        elif isinstance(priority, (int, float)):
            sev = _SEVERITY_MAP.get(int(priority))
            if sev:
                return sev

    # Recovery alerts get Info severity.
    if back_to_normal:
        return AlertSeverity.INFO

    # Anomaly alerts default to Warning; everything else to High.
    rule_type = event.get("ruleType", "")
    if rule_type in _ANOMALY_RULE_TYPES:
        return AlertSeverity.WARNING

    return AlertSeverity.HIGH


def _build_alert_id(event: dict) -> str:
    """Create a stable alert ID from the payload."""
    app_id = event.get("applicationId", "")
    rule_type = event.get("ruleType", "")
    title = event.get("title", "")

    # Include filter values for group-by alerts so each combo gets a
    # unique fingerprint.
    filters = event.get("filters", {})
    filter_str = ""
    if isinstance(filters, dict):
        filter_str = "|".join(
            f"{k}={v}" for k, v in sorted(filters.items())
        )

    seed = f"sematext|{app_id}|{rule_type}|{title}|{filter_str}"
    return hashlib.sha256(seed.encode()).hexdigest()


def _build_labels(event: dict) -> dict:
    """Extract labels from the webhook payload."""
    labels: dict = {}

    if event.get("applicationId"):
        labels["applicationId"] = str(event["applicationId"])

    if event.get("ruleType"):
        labels["ruleType"] = event["ruleType"]

    # Sematext injects filter values for group-by alerts.
    filters = event.get("filters")
    if isinstance(filters, dict):
        for k, v in filters.items():
            labels[f"filter_{k}"] = str(v)

    # Sematext tags (key-value pairs attached to the alert rule)
    tags = event.get("tags")
    if isinstance(tags, dict):
        for k, v in tags.items():
            labels[f"tag_{k}"] = str(v)

    return labels


if __name__ == "__main__":
    pass
