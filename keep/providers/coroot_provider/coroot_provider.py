"""
CorootProvider integrates Coroot with Keep.

Coroot is an open-source eBPF-based APM and observability platform that
automatically discovers service topologies, monitors application health, and
fires alerts based on configurable alerting rules.

This provider supports two modes:

Pull mode:
  Calls the Coroot REST API (``GET /api/project/{project}/alerts``) to fetch
  active and recently-resolved alerts.  Requires a Coroot API key with at
  least *read* access to the target project.

Push mode (webhook):
  Receives Coroot webhook notifications (Alert and Incident templates) via
  Keep's inbound webhook URL.  Coroot uses Go text/template payloads; the
  provider supports the standard JSON alert template format.

Coroot API documentation:
  https://coroot.com/docs/coroot-community-edition/alerting/
  https://github.com/coroot/coroot  (source of truth)
"""

import dataclasses
import datetime
import logging
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class CorootProviderAuthConfig:
    """
    Authentication configuration for the Coroot provider.

    Either ``api_key`` (recommended) or ``username`` + ``password`` can be
    used for pull mode.  Push mode (webhook) requires no credentials.
    """

    host_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Base URL of your Coroot instance",
            "hint": "e.g. https://coroot.example.com or http://localhost:8080",
        }
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Coroot project ID (visible in the URL: /p/{project_id})",
            "hint": "e.g. default or my-project",
        }
    )
    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Coroot API key (Settings → API Keys)",
            "hint": "Recommended over username/password",
            "sensitive": True,
        },
    )
    username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Coroot username (alternative to API key)",
            "hint": "e.g. admin",
        },
    )
    password: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Coroot password (alternative to API key)",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates (disable for self-signed certs)",
        },
    )


class CorootProvider(BaseProvider):
    """
    Receive alert notifications from Coroot via pull or webhook push.

    Pull mode fetches active alerts from the Coroot REST API.
    Push mode receives webhook payloads sent by Coroot's integration settings.
    """

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_TAGS = ["monitoring", "observability", "apm", "ebpf"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read access to Coroot alerts",
            mandatory=True,
            alias="Alerts Read",
        ),
    ]

    # ------------------------------------------------------------------
    # Webhook configuration shown in Keep UI
    # ------------------------------------------------------------------

    webhook_description = "Receive alert notifications from Coroot via webhook"
    webhook_template = ""
    webhook_markdown = """
To connect Coroot alerts to Keep:

1. Open your Coroot instance and navigate to the target **Project**.
2. Go to **Settings** → **Integrations** → **Webhooks**.
3. Click **Add Webhook**.
4. Set the **URL** to:

   `{keep_webhook_api_url}`

5. In the **Alert template** field, enter the following JSON template:

   ```json
   {{json .}}
   ```

   This sends the full alert payload as JSON to Keep.

6. Click **Save**.

Keep will now receive alert and recovery notifications from Coroot automatically.
"""

    # ------------------------------------------------------------------
    # Severity / Status mapping
    # ------------------------------------------------------------------

    # Coroot model.Status string values: ok, info, warning, critical, unknown
    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "ok": AlertSeverity.LOW,
        "unknown": AlertSeverity.INFO,
    }

    # Alert is firing if it has no resolved_at timestamp; suppressed if suppressed=true
    STATUS_MAP = {
        "FIRING": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
        "SUPPRESSED": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._session: Optional[requests.Session] = None

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def dispose(self):
        if self._session:
            self._session.close()
            self._session = None

    def validate_config(self):
        """Validate authentication configuration."""
        self.authentication_config = CorootProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.api_key and not (
            self.authentication_config.username
            and self.authentication_config.password
        ):
            raise ValueError(
                "Either api_key or username+password must be provided for Coroot pull mode."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """Return an authenticated requests.Session."""
        if self._session:
            return self._session

        cfg = self.authentication_config
        session = requests.Session()
        session.verify = cfg.verify_ssl

        if cfg.api_key:
            # Coroot API key auth uses the X-API-Key header (collector.ApiKeyHeader)
            session.headers.update({"X-API-Key": cfg.api_key})
        else:
            # Session-cookie auth: POST /api/login
            login_url = urljoin(cfg.host_url.rstrip("/") + "/", "api/login")
            resp = session.post(
                login_url,
                json={"login": cfg.username, "password": cfg.password},
                timeout=10,
            )
            resp.raise_for_status()

        self._session = session
        return session

    def _alerts_url(self, include_resolved: bool = True) -> str:
        cfg = self.authentication_config
        base = cfg.host_url.rstrip("/")
        project = cfg.project_id
        include = "true" if include_resolved else "false"
        return f"{base}/api/project/{project}/alerts?include_resolved={include}&limit=500"

    # ------------------------------------------------------------------
    # Pull mode: _get_alerts
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch alerts from the Coroot REST API.

        Coroot returns a JSON object with a nested ``alerts`` list.  Each
        alert has the following representative fields:

        ```json
        {
          "id": "abc123",
          "fingerprint": "sha256...",
          "rule_id": "rule-uuid",
          "rule_name": "High error rate",
          "project_id": "default",
          "application_id": {"Namespace": "prod", "Kind": "Deployment", "Name": "api"},
          "severity": "critical",
          "summary": "Error rate exceeded 5%",
          "details": [...],
          "opened_at": 1711700000,
          "resolved_at": 0,
          "suppressed": false,
          "resolved_by": ""
        }
        ```
        """
        try:
            session = self._get_session()
            url = self._alerts_url(include_resolved=True)
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            self.logger.error("Failed to fetch Coroot alerts", extra={"error": str(e)})
            raise

        # Coroot wraps the response in a context envelope; alerts are in data["data"]
        payload = data.get("data") or data
        raw_alerts = payload.get("alerts") or []

        alerts: list[AlertDto] = []
        for raw in raw_alerts:
            try:
                alert = self._map_pull_alert(raw)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                self.logger.warning(
                    "Failed to map Coroot alert",
                    extra={"alert_id": raw.get("id"), "error": str(e)},
                )
        return alerts

    def _map_pull_alert(self, raw: dict) -> Optional[AlertDto]:
        """Map a Coroot API alert dict to an AlertDto."""
        alert_id = raw.get("id", "")
        rule_name = raw.get("rule_name", "Coroot Alert")
        severity_str = (raw.get("severity") or "unknown").lower()
        severity = self.SEVERITY_MAP.get(severity_str, AlertSeverity.INFO)
        summary = raw.get("summary", "")

        # Determine status
        suppressed = raw.get("suppressed", False)
        resolved_at = raw.get("resolved_at", 0)
        manually_resolved_at = raw.get("manually_resolved_at", 0)

        if suppressed:
            status = AlertStatus.SUPPRESSED
        elif resolved_at or manually_resolved_at:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        # Timestamps (Coroot uses Unix epoch ints)
        opened_at = raw.get("opened_at", 0)
        last_received: str
        if isinstance(opened_at, (int, float)) and opened_at > 0:
            last_received = datetime.datetime.utcfromtimestamp(opened_at).isoformat() + "Z"
        else:
            last_received = datetime.datetime.utcnow().isoformat() + "Z"

        # Application identity
        app_id = raw.get("application_id") or {}
        if isinstance(app_id, dict):
            namespace = app_id.get("Namespace", "")
            kind = app_id.get("Kind", "")
            name = app_id.get("Name", "")
            service = f"{namespace}/{kind}/{name}".strip("/")
        else:
            service = str(app_id)

        # Build URL back to Coroot UI
        cfg = self.authentication_config
        base = cfg.host_url.rstrip("/")
        project = cfg.project_id
        alert_url = f"{base}/p/{project}/alerts/{alert_id}" if alert_id else base

        labels = {
            "rule_id": raw.get("rule_id", ""),
            "rule_name": rule_name,
            "project_id": raw.get("project_id", ""),
            "fingerprint": raw.get("fingerprint", ""),
            "suppressed": str(suppressed),
            "resolved_by": raw.get("resolved_by", ""),
            "report": str(raw.get("report", "")),
        }

        return AlertDto(
            id=alert_id or f"coroot-{last_received}",
            name=rule_name,
            description=summary,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["coroot"],
            service=service,
            url=alert_url,
            labels=labels,
        )

    # ------------------------------------------------------------------
    # Push mode: _format_alert (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "CorootProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a Coroot webhook payload into a Keep AlertDto.

        Coroot sends Go text/template-rendered JSON. With the recommended
        template ``{{json .}}`` the payload matches ``AlertTemplateValues``:

        ```json
        {
          "status": "FIRING",
          "project_name": "My Project",
          "application": {"Namespace": "prod", "Kind": "Deployment", "Name": "api"},
          "rule_name": "High error rate",
          "severity": "critical",
          "summary": "Error rate exceeded 5%",
          "details": [...],
          "duration": "5m30s",
          "resolved_by": "",
          "url": "https://coroot.example.com/p/default/alerts/abc123"
        }
        ```

        Coroot also supports Incident and Deployment templates; those payloads
        have a ``status`` field and an ``application`` field.  All variants
        are handled gracefully.
        """

        # --- Status ---
        status_raw = (event.get("status") or "FIRING").strip().upper()
        if status_raw in ("RESOLVED", "CLOSED", "OK"):
            status = AlertStatus.RESOLVED
        elif status_raw in ("SUPPRESSED", "INHIBITED"):
            status = AlertStatus.SUPPRESSED
        else:
            status = AlertStatus.FIRING

        # --- Severity ---
        severity_raw = (event.get("severity") or "").strip().lower()
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "warning": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO,
            "ok": AlertSeverity.LOW,
            "unknown": AlertSeverity.INFO,
        }
        severity = severity_map.get(severity_raw, AlertSeverity.INFO)

        # --- Application identity ---
        app_raw = event.get("application") or {}
        if isinstance(app_raw, dict):
            namespace = app_raw.get("Namespace", "")
            kind = app_raw.get("Kind", "")
            name = app_raw.get("Name", "")
            service = f"{namespace}/{kind}/{name}".strip("/")
        else:
            service = str(app_raw)

        # --- Names / Description ---
        rule_name = event.get("rule_name", "")
        project_name = event.get("project_name", "")
        summary = event.get("summary", "")
        duration = event.get("duration", "")
        resolved_by = event.get("resolved_by", "")

        title = rule_name or f"Coroot Alert ({project_name})"
        description_parts = [summary]
        if duration:
            description_parts.append(f"Duration: {duration}")
        if resolved_by:
            description_parts.append(f"Resolved by: {resolved_by}")
        description = " | ".join(p for p in description_parts if p)

        # --- Alert URL ---
        alert_url = event.get("url", "")

        # --- Identity ---
        last_received = datetime.datetime.utcnow().isoformat() + "Z"

        # Build a stable ID from key fields
        import hashlib
        id_src = f"{project_name}/{service}/{rule_name}/{status_raw}"
        alert_id = "coroot-" + hashlib.sha256(id_src.encode()).hexdigest()[:16]

        labels = {
            "project_name": project_name,
            "rule_name": rule_name,
            "status_raw": status_raw,
            "severity_raw": severity_raw,
            "duration": duration,
            "resolved_by": resolved_by,
        }

        # Include details if present (array of {name, value} or similar)
        details = event.get("details")
        if details and isinstance(details, list):
            for i, d in enumerate(details[:10]):
                if isinstance(d, dict):
                    for k, v in d.items():
                        labels[f"detail_{i}_{k}"] = str(v)

        return AlertDto(
            id=alert_id,
            name=title,
            description=description,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["coroot"],
            service=service,
            url=alert_url,
            labels=labels,
        )
