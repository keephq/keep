"""
CriblProvider - Receive events from Cribl Stream/Edge/Search via HTTP Destination (push)
and pull active alerts from Cribl's REST API.

Cribl (https://cribl.io/) is an observability pipeline platform that routes,
transforms, and enriches telemetry data (logs, metrics, traces) from any source
to any destination.  Keep integrates with Cribl in two ways:

1. **Push (webhook) mode** — Cribl's *HTTP Destination* forwards processed
   events to Keep's webhook endpoint in real-time.  The payload is either a
   single JSON object or a JSON array of objects; each object is converted to
   an ``AlertDto``.

2. **Pull mode** — Keep queries the Cribl Stream REST API to retrieve active
   alerts (search-job results, system notifications, etc.).
"""

import dataclasses
import datetime
import json
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

# ---------------------------------------------------------------------------
# Authentication config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class CriblProviderAuthConfig:
    """Authentication configuration for the Cribl provider.

    For Cribl.Cloud the *api_token* is an organisation-level Bearer token
    (Settings → API Tokens).  For self-hosted Cribl Stream you can use either
    an API token or local username/password credentials (the provider will
    exchange them for a short-lived token automatically).
    """

    # --- connection -----------------------------------------------------------
    deployment_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Cribl instance base URL",
            "hint": (
                "For Cribl.Cloud use https://<your-org>.cribl.cloud — "
                "for self-hosted use http(s)://<host>:9000"
            ),
            "validation": "any_http_url",
        }
    )

    # --- auth: option A — API token (preferred) --------------------------------
    api_token: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Cribl API token (Bearer)",
            "hint": "Create one in Settings → API Tokens inside your Cribl Leader/Cloud UI",
            "sensitive": True,
            "config_sub_group": "api_token",
            "config_main_group": "authentication",
        },
    )

    # --- auth: option B — username + password (self-hosted) --------------------
    username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Cribl admin username",
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )
    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Cribl admin password",
            "sensitive": True,
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify TLS/SSL certificates",
            "hint": "Set to false to allow self-signed certificates in dev environments",
            "type": "switch",
        },
    )

    @pydantic.root_validator
    def check_auth(cls, values):  # noqa: N805
        api_token = values.get("api_token")
        username = values.get("username")
        password = values.get("password")
        if not api_token and not (username and password):
            raise ValueError(
                "Provide either an API token or both username and password."
            )
        return values


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class CriblProvider(BaseProvider):
    """Receive events from Cribl (push) and pull active alerts via REST API."""

    PROVIDER_DISPLAY_NAME = "Cribl"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_TAGS = ["alert", "data"]

    # ------------------------------------------------------------------
    # Webhook (push) configuration
    # ------------------------------------------------------------------
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To forward events from Cribl Stream/Edge to Keep:

1. In Cribl, open **Routing** (Stream) or **Processing** (Edge) and go to **Destinations**.
2. Click **+ Add Destination** and select **HTTP**.
3. Set the **URL** to `{keep_webhook_api_url}`.
4. Under **Authentication**, choose **Manual** and add a request header:
   - **Header name**: `x-api-key`
   - **Value**: `{api_key}`
5. Set **Backpressure Behavior** to *Block* or *Drop* as appropriate.
6. **Save** the destination and attach it to the desired pipeline or route.

Keep will receive events in real time. Each JSON object sent by Cribl is
converted to an alert in Keep.

> **Tip** — to send only specific events, use a Cribl *Filter* expression on
> the route or output group (e.g. `_path == '/logs/alerts'`).
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="system:info",
            description="Read system/version information — validates connectivity.",
            mandatory=True,
            alias="System Info",
        ),
        ProviderScope(
            name="jobs:read",
            description="List and read search job results (required for pull mode).",
            mandatory=False,
            alias="Jobs Read",
        ),
    ]

    # Severity mapping — Cribl itself does not define severity natively;
    # however pipelines commonly enrich events with a ``severity`` or
    # ``level`` field using the values below.
    SEVERITIES_MAP: dict[str, AlertSeverity] = {
        # syslog-style
        "emergency": AlertSeverity.CRITICAL,
        "emerg": AlertSeverity.CRITICAL,
        "alert": AlertSeverity.CRITICAL,
        "critical": AlertSeverity.CRITICAL,
        "crit": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "err": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "notice": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
        # numeric syslog
        "0": AlertSeverity.CRITICAL,
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.CRITICAL,
        "3": AlertSeverity.HIGH,
        "4": AlertSeverity.WARNING,
        "5": AlertSeverity.INFO,
        "6": AlertSeverity.INFO,
        "7": AlertSeverity.LOW,
        # common application conventions
        "fatal": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "unknown": AlertSeverity.INFO,
    }

    STATUS_MAP: dict[str, AlertStatus] = {
        "firing": AlertStatus.FIRING,
        "active": AlertStatus.FIRING,
        "open": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "closed": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "ack": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
    }

    FINGERPRINT_FIELDS = ["_id", "host", "source", "sourcetype"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)
        self._bearer_token: typing.Optional[str] = None

    # ------------------------------------------------------------------
    # Configuration & auth helpers
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        self.authentication_config = CriblProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        pass

    def _base_url(self) -> str:
        url = str(self.authentication_config.deployment_url).rstrip("/")
        return url

    def _get_bearer_token(self) -> str:
        """Return a Bearer token, fetching one via username/password if needed."""
        if self._bearer_token:
            return self._bearer_token

        cfg = self.authentication_config
        if cfg.api_token:
            self._bearer_token = cfg.api_token
            return self._bearer_token

        # Exchange username/password for a token (self-hosted Cribl Stream)
        auth_url = f"{self._base_url()}/api/v1/auth/login"
        try:
            resp = requests.post(
                auth_url,
                json={"username": cfg.username, "password": cfg.password},
                verify=cfg.verify_ssl,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise ProviderException(
                    f"Cribl login response did not contain a token: {data}"
                )
            self._bearer_token = token
            return self._bearer_token
        except requests.RequestException as exc:
            raise ProviderException(f"Failed to authenticate with Cribl: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_bearer_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: typing.Optional[dict] = None) -> dict:
        """Execute a GET request against the Cribl REST API."""
        url = f"{self._base_url()}{path}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                params=params,
                verify=self.authentication_config.verify_ssl,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            raise ProviderException(
                f"Cribl API error {exc.response.status_code} on GET {path}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except requests.RequestException as exc:
            raise ProviderException(f"Cribl request failed on GET {path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}

        # system:info — basic connectivity check
        try:
            self._get("/api/v1/system/info")
            scopes["system:info"] = True
        except ProviderException as exc:
            scopes["system:info"] = str(exc)

        # jobs:read — list search jobs
        try:
            self._get("/api/v1/jobs")
            scopes["jobs:read"] = True
        except ProviderException as exc:
            scopes["jobs:read"] = str(exc)

        return scopes

    # ------------------------------------------------------------------
    # Pull mode — fetch alerts from Cribl REST API
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active events from Cribl Search jobs."""
        alerts: list[AlertDto] = []
        try:
            data = self._get("/api/v1/jobs")
            jobs = data.get("items", data) if isinstance(data, dict) else data
            if not isinstance(jobs, list):
                return alerts

            for job in jobs:
                if not isinstance(job, dict):
                    continue
                # Only bring in completed/running search jobs
                job_status = job.get("status", "")
                if job_status not in ("running", "completed", "done"):
                    continue

                job_id = job.get("id") or job.get("jobId", "")
                if not job_id:
                    continue

                # Fetch result events for this job
                try:
                    result_data = self._get(f"/api/v1/jobs/{job_id}/results", {"count": 100})
                    events = (
                        result_data.get("results", result_data.get("items", []))
                        if isinstance(result_data, dict)
                        else result_data
                    )
                    if isinstance(events, list):
                        for event in events:
                            alert = self._event_to_alert_dto(event, source_job=job)
                            if alert:
                                alerts.append(alert)
                except ProviderException:
                    self.logger.warning(
                        "Could not fetch results for Cribl job %s", job_id
                    )
        except ProviderException as exc:
            self.logger.warning("Cribl pull failed: %s", exc)

        return alerts

    # ------------------------------------------------------------------
    # Push (webhook) mode
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list, provider_instance: "CriblProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Convert a Cribl HTTP Destination payload to AlertDto(s).

        Cribl can send either a single JSON object or a JSON array.  Both
        cases are handled here.
        """
        if isinstance(event, list):
            results = []
            for item in event:
                dto = CriblProvider._event_to_alert_dto(item)
                if dto:
                    results.append(dto)
            return results if results else []

        dto = CriblProvider._event_to_alert_dto(event)
        return dto if dto else AlertDto(name="Cribl Event", source=["cribl"])

    # ------------------------------------------------------------------
    # Shared event → AlertDto conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _event_to_alert_dto(
        event: dict,
        source_job: typing.Optional[dict] = None,
    ) -> typing.Optional[AlertDto]:
        """Map a single Cribl event dictionary to an AlertDto.

        Cribl events are schemaless; we look for common field names used by
        the most popular Cribl packs and pipeline conventions.
        """
        if not isinstance(event, dict):
            return None

        # --- identity ---------------------------------------------------------
        event_id = (
            event.get("_id")
            or event.get("id")
            or event.get("event_id")
            or event.get("guid")
            or None
        )

        # --- name/title -------------------------------------------------------
        name = (
            event.get("title")
            or event.get("name")
            or event.get("alert_name")
            or event.get("message")
            or event.get("msg")
            or event.get("_raw", "")[:120]
            or "Cribl Event"
        )

        # --- description ------------------------------------------------------
        description = (
            event.get("description")
            or event.get("detail")
            or event.get("summary")
            or event.get("_raw", "")
        )

        # --- severity ---------------------------------------------------------
        raw_severity = (
            event.get("severity")
            or event.get("level")
            or event.get("log_level")
            or event.get("priority")
            or event.get("syslog_severity")
            or ""
        )
        severity = CriblProvider.SEVERITIES_MAP.get(
            str(raw_severity).lower(), AlertSeverity.INFO
        )

        # --- status -----------------------------------------------------------
        raw_status = (
            event.get("status")
            or event.get("state")
            or event.get("alert_status")
            or ""
        )
        status = CriblProvider.STATUS_MAP.get(
            str(raw_status).lower(), AlertStatus.FIRING
        )

        # --- timestamp --------------------------------------------------------
        last_received: typing.Optional[datetime.datetime] = None
        ts_raw = event.get("_time") or event.get("timestamp") or event.get("time")
        if ts_raw is not None:
            try:
                if isinstance(ts_raw, (int, float)):
                    # Cribl _time is Unix epoch seconds (may be fractional)
                    last_received = datetime.datetime.fromtimestamp(
                        float(ts_raw), tz=datetime.timezone.utc
                    ).replace(tzinfo=None)
                elif isinstance(ts_raw, str):
                    last_received = datetime.datetime.fromisoformat(
                        ts_raw.replace("Z", "+00:00")
                    )
            except (ValueError, OSError, OverflowError):
                last_received = None

        # --- labels / tags ----------------------------------------------------
        labels: dict[str, str] = {}
        for field in ("labels", "tags", "metadata", "fields"):
            val = event.get(field)
            if isinstance(val, dict):
                labels.update({str(k): str(v) for k, v in val.items()})
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        labels[item] = item
                    elif isinstance(item, dict):
                        k = item.get("key") or item.get("name", "")
                        v = item.get("value", "")
                        if k:
                            labels[str(k)] = str(v)

        # Carry over job metadata as labels when fetched via pull mode
        if source_job:
            for key in ("type", "query", "workerCount"):
                val = source_job.get(key)
                if val is not None:
                    labels[f"cribl_job_{key}"] = str(val)

        # --- build AlertDto ---------------------------------------------------
        return AlertDto(
            id=event_id,
            name=str(name),
            description=str(description) if description else None,
            severity=severity,
            status=status,
            lastReceived=last_received.isoformat() if last_received else None,
            startedAt=last_received.isoformat() if last_received else None,
            # raw Cribl fields
            host=event.get("host"),
            source=["cribl"],
            cribl_source=event.get("source"),
            cribl_sourcetype=event.get("sourcetype"),
            cribl_index=event.get("index"),
            cribl_raw=event.get("_raw"),
            cribl_channel=event.get("cribl_channel"),
            cribl_pipe=event.get("cribl_pipe"),
            labels=labels,
        )


# ---------------------------------------------------------------------------
# Manual test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = {
        "authentication": {
            "deployment_url": os.environ.get(
                "CRIBL_URL", "http://localhost:9000"
            ),
            "api_token": os.environ.get("CRIBL_API_TOKEN"),
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="cribl-test",
        provider_type="cribl",
        provider_config=config,
    )
    print("Scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts[:5]:
        print(" -", a.name, a.severity, a.status)
