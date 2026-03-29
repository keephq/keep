"""
SignozProvider integrates SigNoz with Keep.

SigNoz (https://signoz.io) is an open-source, self-hosted observability platform
built on OpenTelemetry. It provides APM, distributed tracing, metrics monitoring,
and log management with a Prometheus-compatible alerting engine.

Pull mode:
  Calls the SigNoz REST API to fetch active alert rules.
  Endpoint: GET /api/v1/rules

Push mode (webhook):
  Receives alert notifications from SigNoz via its built-in webhook notification
  channel. SigNoz uses an Alertmanager-compatible webhook payload format.

  To configure in SigNoz:
  1. Go to Settings -> Alert Channels -> New Channel
  2. Select "Webhook"
  3. Set the Webhook URL to: {keep_webhook_api_url}
  4. Save and test the channel.

SigNoz API reference:
  https://signoz.io/docs/alerts-management/notification-channel/webhook/
"""

import dataclasses
import datetime
import hashlib
import json
import logging
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SignozProviderAuthConfig:
    """Authentication configuration for the SigNoz provider."""

    host_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Base URL of your SigNoz instance",
            "hint": "e.g. https://signoz.example.com or http://localhost:3301",
            "validation": "any_http_url",
        }
    )
    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SigNoz Personal Access Token (PAT) for API authentication",
            "hint": "Create at Settings -> Access Tokens",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates (disable for self-signed certificates)",
        },
    )


class SignozProvider(BaseProvider):
    """Receive and pull alerts from SigNoz observability platform."""

    PROVIDER_DISPLAY_NAME = "SigNoz"
    PROVIDER_CATEGORY = ["Monitoring", "APM"]
    PROVIDER_TAGS = ["alert", "observability", "tracing", "opentelemetry"]

    webhook_description = (
        "SigNoz sends Alertmanager-compatible webhook payloads when alert rules fire."
    )
    webhook_markdown = """
## Configuring SigNoz to send alerts to Keep

1. In SigNoz, go to **Settings -> Alert Channels**.
2. Click **+ New Alert Channel**.
3. Select **Webhook** as the channel type.
4. Set **Webhook URL** to:
   ```
   {keep_webhook_api_url}
   ```
5. Click **Test** to verify the connection, then **Save**.
6. Assign this channel to one or more alert rules under **Alerts -> Alert Rules**.

Keep will now receive notifications whenever a SigNoz alert rule fires or resolves.

Payload format (Alertmanager-compatible):
```json
{{
  "version": "4",
  "receiver": "keep",
  "status": "firing",
  "alerts": [
    {{
      "status": "firing",
      "labels": {{
        "alertname": "HighErrorRate",
        "severity": "critical",
        "service": "frontend"
      }},
      "annotations": {{
        "description": "Error rate exceeded 5%",
        "summary": "High error rate on frontend"
      }},
      "startsAt": "2024-01-01T00:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "https://signoz.example.com/alerts",
      "fingerprint": "abc123"
    }}
  ]
}}
```
"""

    # Severity map: SigNoz/Alertmanager severity labels -> Keep severity
    SEVERITIES_MAP: dict = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "information": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "ok": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
        # Priority levels (p1=most critical, p5=low)
        "p1": AlertSeverity.CRITICAL,
        "p2": AlertSeverity.HIGH,
        "p3": AlertSeverity.WARNING,
        "p4": AlertSeverity.INFO,
        "p5": AlertSeverity.LOW,
    }

    # Status map: SigNoz/Alertmanager status -> Keep status
    STATUS_MAP: dict = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "inactive": AlertStatus.RESOLVED,
        "pending": AlertStatus.PENDING,
        "suppressed": AlertStatus.SUPPRESSED,
        "inhibited": AlertStatus.SUPPRESSED,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read alert rules and their firing state via SigNoz API",
            mandatory=False,
            documentation_url="https://signoz.io/docs/alerts-management/",
        )
    ]

    FINGERPRINT_FIELDS = ["fingerprint", "alertname", "service"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SignozProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    # ------------------------------------------------------------------
    # URL / header helpers
    # ------------------------------------------------------------------

    def _get_base_url(self) -> str:
        """Return the base URL with trailing slash removed."""
        return self.authentication_config.host_url.rstrip("/")

    def _build_headers(self) -> dict:
        """Build HTTP headers for SigNoz API requests."""
        headers: dict = {"Content-Type": "application/json"}
        api_key = self.authentication_config.api_key
        if api_key:
            headers["SIGNOZ-API-KEY"] = api_key
        return headers

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict:
        """Validate provider scopes by testing the alerts API endpoint."""
        validated: dict = {}
        try:
            url = f"{self._get_base_url()}/api/v1/rules"
            resp = requests.get(
                url,
                headers=self._build_headers(),
                verify=self.authentication_config.verify_ssl,
                timeout=10,
            )
            if resp.status_code in (200, 204):
                validated["alerts:read"] = True
            else:
                validated["alerts:read"] = (
                    f"Unexpected HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as exc:
            validated["alerts:read"] = str(exc)
        return validated

    # ------------------------------------------------------------------
    # Pull mode
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list:
        """
        Pull alert instances from SigNoz.

        SigNoz exposes active alert rules at GET /api/v1/rules.
        """
        url = f"{self._get_base_url()}/api/v1/rules"
        resp = requests.get(
            url,
            headers=self._build_headers(),
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # Unwrap common envelope formats
        if isinstance(data, dict):
            inner = (
                data.get("data")
                or data.get("alerts")
                or data.get("rules")
            )
            if isinstance(inner, list):
                data = inner
            else:
                data = [data]

        if not isinstance(data, list):
            return []

        alerts = []
        for item in data:
            try:
                dto = self._alert_dict_to_dto(item)
                alerts.append(dto)
            except Exception as exc:
                self.logger.warning(
                    "Failed to map SigNoz alert",
                    extra={"error": str(exc)},
                )
        return alerts

    def _alert_dict_to_dto(self, alert: dict) -> AlertDto:
        """
        Convert a single SigNoz/Alertmanager alert dict to an AlertDto.
        """
        labels: dict = alert.get("labels") or {}
        annotations: dict = alert.get("annotations") or {}

        # Alert name
        alert_name = (
            labels.get("alertname")
            or alert.get("alert")
            or alert.get("name")
            or "SigNoz Alert"
        )

        # Status - can be string "firing" or dict {"state": "suppressed"}
        raw_status = alert.get("status", "")
        if isinstance(raw_status, dict):
            status_str = (raw_status.get("state") or "").lower()
        else:
            status_str = str(raw_status).lower()
        status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        # Severity from labels
        severity_raw = (
            labels.get("severity")
            or labels.get("priority")
            or annotations.get("severity")
            or "info"
        ).lower()
        severity = self.SEVERITIES_MAP.get(severity_raw, AlertSeverity.INFO)

        # Timestamps
        starts_at_str = alert.get("startsAt") or alert.get("activeAt") or ""
        ends_at_str = alert.get("endsAt") or ""
        # "0001-01-01" is Alertmanager's null sentinel
        if ends_at_str.startswith("0001-"):
            ends_at_str = ""

        def _parse_ts(ts: str):
            if not ts:
                return None
            try:
                return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        started_at = _parse_ts(starts_at_str) or datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc
        )
        ended_at = _parse_ts(ends_at_str)

        last_received = (ended_at or started_at).isoformat()

        description = (
            annotations.get("description")
            or annotations.get("summary")
            or alert_name
        )

        service = (
            labels.get("service")
            or labels.get("job")
            or labels.get("instance")
            or ""
        )

        fingerprint = alert.get(
            "fingerprint",
            "signoz-"
            + hashlib.sha256(
                f"{alert_name}/{service}/{severity_raw}".encode()
            ).hexdigest()[:16],
        )

        url_field = alert.get("generatorURL") or alert.get("url") or ""

        keep_labels = {k: str(v) for k, v in labels.items()}
        keep_labels["rule_name"] = alert_name

        return AlertDto(
            id=fingerprint,
            name=alert_name,
            description=description,
            status=status,
            severity=severity,
            startedAt=started_at.isoformat(),
            endedAt=ended_at.isoformat() if ended_at else None,
            lastReceived=last_received,
            source=["signoz"],
            service=service,
            url=url_field,
            labels=keep_labels,
            fingerprint=fingerprint,
        )

    # ------------------------------------------------------------------
    # Push mode (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_alertmanager_payload(payload: dict) -> list:
        """
        Parse an Alertmanager-format webhook payload into AlertDto objects.
        """
        # Unwrap {"data": {...}} envelope if present
        if "data" in payload and isinstance(payload.get("data"), dict):
            payload = payload["data"]

        alerts_raw = payload.get("alerts")
        if isinstance(alerts_raw, list) and alerts_raw:
            raw_list = alerts_raw
        else:
            # Flat payload — treat as single alert
            raw_list = [payload]

        envelope_status = payload.get("status", "")
        common_labels: dict = payload.get("commonLabels") or {}
        common_annotations: dict = payload.get("commonAnnotations") or {}
        external_url: str = payload.get("externalURL") or ""

        results = []
        for raw in raw_list:
            try:
                dto = SignozProvider._map_alertmanager_alert(
                    raw,
                    envelope_status=envelope_status,
                    common_labels=common_labels,
                    common_annotations=common_annotations,
                    external_url=external_url,
                )
                results.append(dto)
            except Exception:
                logger.warning("Failed to map SigNoz webhook alert", exc_info=True)
        return results

    @staticmethod
    def _map_alertmanager_alert(
        alert: dict,
        *,
        envelope_status: str = "",
        common_labels: dict = None,
        common_annotations: dict = None,
        external_url: str = "",
    ) -> AlertDto:
        """Map a single Alertmanager alert dict to an AlertDto."""
        common_labels = common_labels or {}
        common_annotations = common_annotations or {}

        labels: dict = {**common_labels, **(alert.get("labels") or {})}
        annotations: dict = {**common_annotations, **(alert.get("annotations") or {})}

        alert_name = labels.get("alertname", "SigNoz Alert")

        raw_status = (alert.get("status") or envelope_status or "firing").lower()
        if isinstance(raw_status, dict):
            raw_status = (raw_status.get("state") or "").lower()
        status = SignozProvider.STATUS_MAP.get(raw_status, AlertStatus.FIRING)

        severity_raw = (
            labels.get("severity") or labels.get("priority") or "info"
        ).lower()
        severity = SignozProvider.SEVERITIES_MAP.get(severity_raw, AlertSeverity.INFO)

        starts_at_str = alert.get("startsAt") or ""
        ends_at_str = alert.get("endsAt") or ""
        if ends_at_str.startswith("0001-"):
            ends_at_str = ""

        def _parse_ts(ts: str):
            if not ts:
                return None
            try:
                return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        started_at = _parse_ts(starts_at_str) or datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc
        )
        ended_at = _parse_ts(ends_at_str)
        last_received = (ended_at or started_at).isoformat()

        description = (
            annotations.get("description")
            or annotations.get("summary")
            or alert_name
        )

        service = (
            labels.get("service")
            or labels.get("job")
            or labels.get("instance")
            or ""
        )

        fingerprint = alert.get(
            "fingerprint",
            "signoz-"
            + hashlib.sha256(
                f"{alert_name}/{service}/{severity_raw}".encode()
            ).hexdigest()[:16],
        )

        url_field = alert.get("generatorURL") or external_url or ""

        keep_labels = {k: str(v) for k, v in labels.items()}

        return AlertDto(
            id=fingerprint,
            name=alert_name,
            description=description,
            status=status,
            severity=severity,
            startedAt=started_at.isoformat(),
            endedAt=ended_at.isoformat() if ended_at else None,
            lastReceived=last_received,
            source=["signoz"],
            service=service,
            url=url_field,
            labels=keep_labels,
            fingerprint=fingerprint,
        )

    def _format_webhook_event(
        self,
        tenant_id: str,
        provider_id: str,
        payload,
    ):
        """
        Convert a raw SigNoz webhook payload (bytes or dict) into AlertDto(s).

        Raises ValueError for invalid JSON byte payloads.
        """
        if isinstance(payload, bytes):
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in SigNoz webhook payload: {exc}"
                ) from exc
        else:
            event = payload

        alerts = self._parse_alertmanager_payload(event)

        if len(alerts) == 1:
            return alerts[0]
        return alerts

    @staticmethod
    def _format_alert(event: dict, provider_instance: "SignozProvider" = None):
        """Static entry point called by Keep's webhook router."""
        alerts = SignozProvider._parse_alertmanager_payload(event)
        if len(alerts) == 1:
            return alerts[0]
        return alerts


if __name__ == "__main__":
    pass
