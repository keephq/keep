"""
MezmoProvider integrates Mezmo (formerly LogDNA) with Keep.

Mezmo is a log management and observability platform that allows teams to
aggregate, monitor, and analyse log data.  This provider receives alert
notifications from Mezmo via its webhook (Webhooks alert channel) feature.

Mezmo webhook documentation:
  https://docs.mezmo.com/docs/alerts
  https://docs.mezmo.com/docs/webhooks-channel
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
class MezmoProviderAuthConfig:
    """
    MezmoProviderAuthConfig — no outbound credentials required.

    Mezmo pushes alerts to Keep via webhook.  Keep only acts as a receiver.
    """

    pass


class MezmoProvider(BaseProvider):
    """
    Receive alert notifications from Mezmo (formerly LogDNA) via webhook.

    Mezmo sends a JSON payload to the Keep inbound webhook URL when a
    log-based alert triggers or recovers.  This provider maps those payloads
    to Keep ``AlertDto`` objects.

    Mezmo alert webhook payload example:
    ```json
    {
      "account": "mycompany",
      "alerts": [
        {
          "name": "Error Rate Spike",
          "description": "More than 100 errors in 5 minutes",
          "query": "level:error",
          "type": "presence",
          "lines": 127,
          "label": "production",
          "severity": "CRITICAL",
          "url": "https://app.mezmo.com/...",
          "triggered_at": "2026-03-29T10:00:00Z",
          "ended_at": null,
          "resolved": false
        }
      ]
    }
    ```
    """

    PROVIDER_DISPLAY_NAME = "Mezmo"
    PROVIDER_TAGS = ["monitoring", "logging", "observability"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    # ------------------------------------------------------------------
    # Webhook configuration shown in Keep UI
    # ------------------------------------------------------------------

    webhook_description = "Receive alert notifications from Mezmo (formerly LogDNA)"
    webhook_template = ""
    webhook_markdown = """
To connect Mezmo alerts to Keep:

1. Log in to [Mezmo](https://app.mezmo.com/).
2. Navigate to **Settings** → **Alerts** → **Alert Channels**.
3. Click **Add Channel** and choose **Webhook**.
4. Give the channel a name (e.g. "Keep").
5. Set **URL** to:

   `{keep_webhook_api_url}`

6. Set **Method** to `POST` and **Content Type** to `application/json`.
7. Click **Save**.
8. Open any **Alert** rule and add the new webhook channel in the **Alert Channels** section.
9. Click **Save**.

Keep will now receive alert and recovery notifications from Mezmo.
"""

    # ------------------------------------------------------------------
    # Alert mapping tables
    # ------------------------------------------------------------------

    # Mezmo severity strings → Keep AlertSeverity
    # Mezmo uses: CRITICAL, ERROR, WARNING, INFO, DEBUG (and numeric variants)
    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "fatal": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warn": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
        "trace": AlertSeverity.LOW,
        # Numeric level equivalents (syslog-style) sometimes sent by Mezmo
        "0": AlertSeverity.CRITICAL,   # Emergency
        "1": AlertSeverity.CRITICAL,   # Alert
        "2": AlertSeverity.CRITICAL,   # Critical
        "3": AlertSeverity.HIGH,       # Error
        "4": AlertSeverity.WARNING,    # Warning
        "5": AlertSeverity.INFO,       # Notice
        "6": AlertSeverity.INFO,       # Informational
        "7": AlertSeverity.LOW,        # Debug
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
        self.authentication_config = MezmoProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Push mode: _format_alert (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MezmoProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a Mezmo webhook payload into one or more Keep ``AlertDto`` objects.

        Mezmo can send multiple alerts in a single webhook call (the ``alerts``
        array).  Each alert in the array is converted into a separate ``AlertDto``.
        If the payload is a flat single-alert object (no ``alerts`` key), it is
        treated as a single alert.
        """
        account = event.get("account", "")

        # Mezmo may send a list of alerts or a single alert object
        raw_alerts = event.get("alerts")
        if raw_alerts is None:
            # Treat the top-level dict as a single alert
            raw_alerts = [event]

        if not isinstance(raw_alerts, list):
            raw_alerts = [raw_alerts]

        dtos: list[AlertDto] = []
        for alert in raw_alerts:
            dtos.append(MezmoProvider._convert_single_alert(alert, account))

        if len(dtos) == 1:
            return dtos[0]
        return dtos

    @staticmethod
    def _convert_single_alert(alert: dict, account: str = "") -> AlertDto:
        """Convert a single Mezmo alert object to an AlertDto."""

        # --- Status ---
        resolved = alert.get("resolved", False)
        ended_at = alert.get("ended_at")
        if resolved or ended_at:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        # --- Severity ---
        severity_raw = (alert.get("severity") or alert.get("level") or "").strip().lower()
        severity = MezmoProvider.SEVERITY_MAP.get(severity_raw, AlertSeverity.INFO)

        # Recovery alerts cap severity at INFO
        if status == AlertStatus.RESOLVED and severity in (
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
            AlertSeverity.WARNING,
        ):
            severity = AlertSeverity.INFO

        # --- Identity ---
        alert_name = alert.get("name", "Mezmo Alert")
        triggered_at = alert.get("triggered_at", "")
        # Unique id: account + alert_name + triggered_at
        safe_name = alert_name.replace(" ", "_").lower()
        alert_id = f"mezmo-{account}-{safe_name}-{triggered_at}" if triggered_at else f"mezmo-{account}-{safe_name}"

        # --- Timestamps ---
        last_received = triggered_at or datetime.datetime.utcnow().isoformat() + "Z"

        # --- Description ---
        description = alert.get("description", "")
        lines = alert.get("lines")
        if lines is not None:
            line_context = f"Matched lines: {lines}"
            description = f"{description} [{line_context}]" if description else line_context

        # --- Labels ---
        query = alert.get("query", "")
        alert_type = alert.get("type", "")
        label = alert.get("label", "")
        alert_url = alert.get("url", "")

        labels = {
            "account": account,
            "query": query,
            "alertType": alert_type,
            "label": label,
            "resolved": str(resolved),
            "severity": alert.get("severity") or alert.get("level") or "",
        }

        return AlertDto(
            id=alert_id,
            name=alert_name,
            description=description,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["mezmo"],
            service=label or account,
            url=alert_url,
            labels=labels,
        )
