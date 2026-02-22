"""
SolarWinds Orion is a network and infrastructure monitoring platform.
This provider ingests alert webhooks from SolarWinds Orion and converts
them into Keep's unified AlertDto format.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SolarwindsProvider(BaseProvider):
    """Get alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Infrastructure"]
    FINGERPRINT_FIELDS = ["AlertActiveID"]

    # SolarWinds Orion severity integers (0–3)
    # Reference: SolarWinds Platform SDK / Alert Manager
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.CRITICAL,  # Fatal — map to CRITICAL (Keep has no Fatal tier)
    }

    # Fallback string-based severity names emitted by some Orion versions
    SEVERITIES_MAP_STR = {
        "information": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "fatal": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
    }

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Configuring SolarWinds Orion Webhook Alerts

### Prerequisites
- SolarWinds Orion Platform 2020.2 or later
- **Alerts & Activity › Alert Manager** access
- A Keep webhook URL (copy from the provider page)

---

### Step 1 – Create an Alert Action (Webhook)

1. Log in to your **SolarWinds Web Console**.
2. Navigate to **Alerts & Activity › Alerts**.
3. Open an existing alert or click **Manage Alerts › New Alert**.
4. In the alert definition, go to the **Trigger Actions** tab.
5. Click **Add Action**, then select **Send a GET or POST Request to a Web Server**.

---

### Step 2 – Configure the HTTP POST request

| Field | Value |
|---|---|
| **Name** | Keep – webhook |
| **URL** | `<your Keep webhook URL>` |
| **Method** | `POST` |
| **Content Type** | `application/json` |

Paste the following JSON body (Orion variable substitution syntax):

```json
{
  "AlertName":        "${N=Alerting;M=AlertName}",
  "AlertMessage":     "${N=Alerting;M=AlertMessage}",
  "AlertDescription": "${N=Alerting;M=AlertDescription}",
  "AlertDetailsUrl":  "${N=Alerting;M=AlertDetailsUrl}",
  "AlertObjectID":    "${N=Alerting;M=AlertObjectID}",
  "AlertActiveID":    "${N=Alerting;M=AlertActiveID}",
  "Severity":         "${N=Alerting;M=Severity}",
  "Acknowledged":     "${N=Alerting;M=Acknowledged}",
  "TimeOfAlert":      "${N=Alerting;M=TimeOfAlert}",
  "NodeName":         "${N=SwisEntity;M=NodeName}",
  "NodeCaption":      "${N=SwisEntity;M=Caption}",
  "IP_Address":       "${N=SwisEntity;M=IP_Address}"
}
```

> **Tip:** The variables above are standard Orion macro substitutions. Adjust the
> `N=SwisEntity` namespace to `N=Interfaces` or another entity type if you are
> alerting on non-node objects.

---

### Step 3 – Reset / Resolve Action (optional)

To automatically resolve alerts in Keep when SolarWinds clears them:

1. Go to the **Reset Actions** tab of the same alert definition.
2. Add another **Send POST Request** action pointing to the same Keep webhook URL.
3. Use the identical JSON body — Keep will detect the reset via the `Acknowledged`
   or `Severity` fields and mark the alert as **Resolved**.

---

### Step 4 – Save and Test

1. Click **Submit** to save the alert definition.
2. Trigger the alert manually (or wait for a real event) and confirm it appears
   in your Keep **Alert Feed**.
3. If you do not see the alert, check **SolarWinds › Admin › Audit Trail** for
   HTTP response codes and retry.

---

### Troubleshooting

- **401 Unauthorized** – Verify the webhook URL includes the correct API key.
- **No alerts received** – Confirm the alert is in **Active** state and that
  the POST action is in **Trigger Actions**, not only **Reset Actions**.
- **Missing fields** – Some Orion entity types expose different SWIS namespaces.
  Open **SWIS Query Tool** (`npm query`) to discover available properties.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """SolarWinds webhook provider requires no outbound credentials."""
        pass

    def dispose(self):
        """No cleanup required."""
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["SolarwindsProvider"] = None
    ) -> AlertDto:
        """
        Convert a raw SolarWinds Orion webhook payload into an AlertDto.

        SolarWinds delivers alert payloads as JSON via HTTP POST. The fields
        below are the standard Orion alert macro variables; additional custom
        fields are preserved in the ``extra`` dict.
        """
        # --- Severity ---
        raw_severity = event.get("Severity")
        severity = AlertSeverity.INFO  # safe default

        if isinstance(raw_severity, int):
            severity = SolarwindsProvider.SEVERITIES_MAP.get(raw_severity, AlertSeverity.INFO)
        elif isinstance(raw_severity, str):
            # Orion sometimes sends the integer as a string
            if raw_severity.isdigit():
                severity = SolarwindsProvider.SEVERITIES_MAP.get(
                    int(raw_severity), AlertSeverity.INFO
                )
            else:
                severity = SolarwindsProvider.SEVERITIES_MAP_STR.get(
                    raw_severity.lower(), AlertSeverity.INFO
                )

        # --- Status ---
        # Check for explicit reset/resolved status (sent by Reset Actions)
        alert_status_raw = str(event.get("AlertStatus", "")).lower()
        if alert_status_raw in ("reset", "cleared", "resolved"):
            status = AlertStatus.RESOLVED
        else:
            # SolarWinds "Acknowledged" is a boolean (or "True"/"False" string).
            acknowledged_raw = event.get("Acknowledged", False)
            if isinstance(acknowledged_raw, str):
                acknowledged = acknowledged_raw.strip().lower() in ("true", "1", "yes")
            else:
                acknowledged = bool(acknowledged_raw)

            status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING

        # --- Timestamp ---
        time_of_alert = event.get("TimeOfAlert")
        last_received: Optional[str] = None
        if time_of_alert:
            try:
                # Orion typically sends ISO-8601; handle both Z and offset forms
                normalized = time_of_alert.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                last_received = parsed.isoformat()
            except (ValueError, AttributeError):
                logger.warning(
                    "SolarwindsProvider: could not parse TimeOfAlert %r", time_of_alert
                )
                last_received = datetime.now(tz=timezone.utc).isoformat()

        # --- Core AlertDto fields ---
        alert_id = str(event.get("AlertActiveID") or event.get("AlertObjectID") or "")
        name = event.get("AlertName", "SolarWinds Alert")
        description = event.get("AlertDescription") or event.get("AlertMessage", "")
        url = event.get("AlertDetailsUrl")
        node_name = event.get("NodeName") or event.get("NodeCaption")

        # Collect any non-standard fields the customer added to the payload.
        # IP_Address is intentionally excluded from known_keys so it flows
        # through **extra into AlertDto (AlertDto extra="allow").
        known_keys = {
            "AlertName", "AlertMessage", "AlertDescription", "AlertDetailsUrl",
            "AlertObjectID", "AlertActiveID", "Severity", "Acknowledged",
            "AlertStatus", "TimeOfAlert", "NodeName", "NodeCaption",
        }
        extra = {k: v for k, v in event.items() if k not in known_keys}

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            url=url,
            host=node_name,
            source=["solarwinds"],
            # Pass through the full payload so rules / playbooks can reference
            # any Orion field without losing data.
            **extra,
        )
