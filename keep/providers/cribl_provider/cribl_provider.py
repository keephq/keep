"""
CriblProvider is a class that integrates Keep with Cribl Stream / Cribl Edge.

Cribl is a universal data pipeline for logs, metrics, traces, and security data.

Supports:
  - Push mode  : receive events forwarded from Cribl via its HTTP Destination
  - Pull mode  : poll the Cribl REST API for worker-group health, pipeline
                 errors, and active job failures
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
class CriblProviderAuthConfig:
    """
    Cribl authentication configuration.

    Supports either Bearer-token (api_key) or username + password.
    The api_url is only needed for pull mode; push mode is always available.
    """

    api_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "Cribl REST API base URL (e.g. https://cribl.example.com)",
            "hint": "https://cribl.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        },
        default="",
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Cribl API bearer token (preferred over username/password)",
            "hint": "Bearer token from Cribl Settings > API",
            "sensitive": True,
        },
        default="",
    )

    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Cribl username (used when api_key is not provided)",
            "hint": "admin",
            "sensitive": False,
        },
        default="",
    )

    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Cribl password",
            "hint": "P@ssw0rd",
            "sensitive": True,
        },
        default="",
    )

    worker_group: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Cribl worker group to query (default: 'default')",
            "hint": "default",
            "sensitive": False,
        },
        default="default",
    )


class CriblProvider(BaseProvider):
    """
    Keep provider for Cribl Stream / Cribl Edge.

    Push mode: Cribl's HTTP Destination forwards events as JSON to Keep's
    webhook endpoint. The payload may be a single JSON object or a JSON array
    of event objects (Cribl batching).

    Pull mode: queries the Cribl REST API for worker-group status and active
    pipeline job failures; surfaces unhealthy workers and failed pipelines as
    Keep alerts.
    """

    PROVIDER_DISPLAY_NAME = "Cribl"
    PROVIDER_CATEGORY = ["Monitoring", "Data Pipeline"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="system:read",
            description="Read worker-group status and pipeline health via the Cribl REST API",
            mandatory=False,
            documentation_url="https://docs.cribl.io/stream/api-reference/",
        ),
    ]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To forward events from Cribl to Keep via the HTTP Destination:

1. In Cribl Stream, navigate to **Routing > QuickConnect** (or open your pipeline in the Pipelines editor).
2. Add an **HTTP Destination** output.
3. Set **URL** to `{keep_webhook_api_url}`.
4. Under **Headers**, add:
   - Key: `X-API-KEY`  Value: `{api_key}`
5. Set **Method** to `POST` and **Data Format** to `JSON`.
6. In your pipeline, connect the sources whose events you want to forward to this destination.
7. Commit and deploy the configuration.

Keep will now receive events from all Cribl pipelines routed to this destination.
"""

    # Cribl severity strings → Keep severity
    SEVERITY_MAP: dict[str, AlertSeverity] = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
        "low": AlertSeverity.LOW,
    }

    # Cribl event status strings → Keep status
    STATUS_MAP: dict[str, AlertStatus] = {
        "firing": AlertStatus.FIRING,
        "active": AlertStatus.FIRING,
        "failed": AlertStatus.FIRING,
        "error": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "cleared": AlertStatus.RESOLVED,
        "suppressed": AlertStatus.SUPPRESSED,
    }

    FINGERPRINT_FIELDS = ["cribl_source", "host", "name"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None

    def dispose(self) -> None:
        pass

    def validate_config(self) -> None:
        self.authentication_config = CriblProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _get_auth_headers(self) -> dict:
        """Return HTTP headers for Cribl REST API calls."""
        if self.authentication_config.api_key:
            return {"Authorization": f"Bearer {self.authentication_config.api_key}"}

        # Username / password → obtain ephemeral bearer token
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}

        token = self._login()
        return {"Authorization": f"Bearer {token}"}

    def _login(self) -> str:
        """Authenticate with username/password and cache the access token."""
        url = urljoin(
            str(self.authentication_config.api_url), "/api/v1/auth/login"
        )
        resp = requests.post(
            url,
            json={
                "username": self.authentication_config.username,
                "password": self.authentication_config.password,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("token", "")
        self._access_token = token
        return token

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        """Check that the provided credentials can reach the Cribl REST API."""
        if not self.authentication_config.api_url:
            return {"system:read": "api_url is not configured"}

        try:
            url = urljoin(
                str(self.authentication_config.api_url),
                f"/api/v1/m/{self.authentication_config.worker_group}/system/info",
            )
            headers = self._get_auth_headers()
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return {"system:read": True}
            return {"system:read": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"system:read": str(e)}

    # ------------------------------------------------------------------
    # Pull mode
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull mode: query Cribl REST API for unhealthy workers and failed pipelines.

        Returns Keep AlertDto objects for each problem found.
        """
        if not self.authentication_config.api_url:
            self.logger.debug("api_url not configured; skipping pull mode")
            return []

        alerts: list[AlertDto] = []
        group = self.authentication_config.worker_group
        base = str(self.authentication_config.api_url)
        headers = self._get_auth_headers()

        # --- worker-group / system health ---
        try:
            alerts.extend(self._pull_worker_health(base, group, headers))
        except Exception as exc:
            self.logger.warning("Failed to pull Cribl worker health: %s", exc)

        # --- pipeline job failures ---
        try:
            alerts.extend(self._pull_pipeline_jobs(base, group, headers))
        except Exception as exc:
            self.logger.warning("Failed to pull Cribl pipeline jobs: %s", exc)

        return alerts

    def _pull_worker_health(
        self, base: str, group: str, headers: dict
    ) -> list[AlertDto]:
        """Fetch worker-group summary and surface unhealthy workers."""
        url = urljoin(base, f"/api/v1/m/{group}/system/info")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        alerts: list[AlertDto] = []
        items = data if isinstance(data, list) else data.get("items", [data])
        for item in items:
            status_str = str(item.get("status", "")).lower()
            if status_str in ("ok", "running", ""):
                continue  # healthy worker — skip

            alert = AlertDto(
                id=item.get("id", item.get("guid", "unknown")),
                name=f"Cribl worker unhealthy: {item.get('hostname', 'unknown')}",
                description=(
                    f"Cribl worker {item.get('hostname', 'unknown')} reported "
                    f"status '{status_str}'"
                ),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.FIRING,
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source=["cribl"],
                labels={
                    "worker_id": str(item.get("id", "")),
                    "hostname": str(item.get("hostname", "")),
                    "group": group,
                },
            )
            alerts.append(alert)

        return alerts

    def _pull_pipeline_jobs(
        self, base: str, group: str, headers: dict
    ) -> list[AlertDto]:
        """Fetch running/failed pipeline jobs and surface failures."""
        url = urljoin(base, f"/api/v1/m/{group}/jobs")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        alerts: list[AlertDto] = []
        items = data if isinstance(data, list) else data.get("items", [])
        for job in items:
            status_str = str(job.get("status", "")).lower()
            if status_str not in ("failed", "error", "cancelled"):
                continue

            pipeline_id = job.get("pipelineId") or job.get("id", "unknown")
            alert = AlertDto(
                id=f"cribl-job-{job.get('id', pipeline_id)}",
                name=f"Cribl pipeline job failed: {pipeline_id}",
                description=(
                    f"Pipeline job '{pipeline_id}' finished with status "
                    f"'{status_str}': {job.get('message', '')}"
                ),
                severity=AlertSeverity.HIGH,
                status=AlertStatus.FIRING,
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source=["cribl"],
                labels={
                    "pipeline_id": str(pipeline_id),
                    "job_id": str(job.get("id", "")),
                    "group": group,
                    "job_status": status_str,
                },
            )
            alerts.append(alert)

        return alerts

    # ------------------------------------------------------------------
    # Push / webhook mode
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "CriblProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a Cribl HTTP Destination payload to one or more Keep AlertDto
        objects.

        Cribl may POST:
          - A single JSON object  → one AlertDto
          - A JSON array          → list[AlertDto]  (Cribl batching)
          - A wrapper object with an "events" / "results" key
        """
        # Handle array-of-events (Cribl batching)
        if isinstance(event, list):
            alerts = []
            for item in event:
                if isinstance(item, dict):
                    a = CriblProvider._format_single_event(item)
                    if a is not None:
                        alerts.append(a)
            return alerts if alerts else []

        # Handle wrapper with nested events
        for key in ("events", "results", "records", "items"):
            if key in event and isinstance(event[key], list):
                alerts = []
                for item in event[key]:
                    if isinstance(item, dict):
                        a = CriblProvider._format_single_event(item)
                        if a is not None:
                            alerts.append(a)
                return alerts if alerts else []

        # Single event object
        a = CriblProvider._format_single_event(event)
        return a if a is not None else AlertDto(
            id="cribl-unknown",
            name="Cribl event",
            severity=AlertSeverity.INFO,
            status=AlertStatus.FIRING,
            source=["cribl"],
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    @staticmethod
    def _format_single_event(event: dict) -> Optional[AlertDto]:
        """Convert a single Cribl event dict to an AlertDto."""
        if not event:
            return None

        # --- identity ---
        event_id = (
            event.get("id")
            or event.get("_id")
            or event.get("event_id")
            or event.get("guid")
            or f"cribl-{hash(str(sorted(event.items()))) & 0xFFFFFFFF:08x}"
        )

        # --- name / description ---
        name = (
            event.get("name")
            or event.get("title")
            or event.get("alert_name")
            or event.get("source")
            or event.get("_raw", "")[:80]
            or "Cribl event"
        )
        description = (
            event.get("description")
            or event.get("message")
            or event.get("msg")
            or event.get("_raw", "")
            or ""
        )

        # --- severity ---
        raw_severity = (
            event.get("severity")
            or event.get("level")
            or event.get("cribl_severity")
            or event.get("log_level")
            or event.get("LogLevel")
            or "info"
        )
        severity = CriblProvider.SEVERITY_MAP.get(
            str(raw_severity).lower(), AlertSeverity.INFO
        )

        # --- status ---
        raw_status = (
            event.get("status")
            or event.get("alert_status")
            or event.get("state")
            or "firing"
        )
        status = CriblProvider.STATUS_MAP.get(
            str(raw_status).lower(), AlertStatus.FIRING
        )

        # --- timestamp ---
        raw_time = (
            event.get("lastReceived")
            or event.get("timestamp")
            or event.get("_time")
            or event.get("time")
        )
        if isinstance(raw_time, (int, float)):
            # Cribl uses Unix seconds or milliseconds
            if raw_time > 1e12:
                raw_time = raw_time / 1000.0
            last_received = datetime.datetime.fromtimestamp(
                raw_time, tz=datetime.timezone.utc
            ).isoformat()
        else:
            last_received = str(raw_time) if raw_time else datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        # --- labels ---
        labels: dict = {}
        for field in ("host", "source", "cribl_source", "namespace", "env",
                      "service", "pipeline", "worker_group"):
            val = event.get(field)
            if val is not None:
                labels[field] = str(val)

        # Include arbitrary top-level string/numeric fields as labels
        for k, v in event.items():
            if k not in labels and isinstance(v, (str, int, float, bool)):
                labels[k] = str(v)

        return AlertDto(
            id=str(event_id),
            name=str(name),
            description=str(description),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["cribl"],
            labels=labels,
            cribl_source=event.get("cribl_source") or event.get("source"),
            host=event.get("host"),
        )


if __name__ == "__main__":
    pass
