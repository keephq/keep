"""
Falco Provider — ingests runtime-security alerts from Falco into Keep.

Supports two modes:
  1. **Push (webhook)** — Falco/Falcosidekick HTTP output sends JSON events to
     Keep's webhook endpoint.  No credentials needed; Keep parses and stores them.
  2. **Pull (Falcosidekick UI API)** — Keep periodically fetches the event list
     from a running Falcosidekick instance (requires ``sidekick_url``).

Falco priority → Keep severity mapping
  Emergency / Alert / Critical / Error → CRITICAL
  Warning                              → WARNING
  Notice / Informational               → INFO
  Debug                                → LOW

References
----------
- Falco docs:          https://falco.org/docs/
- Falcosidekick:       https://github.com/falcosecurity/falcosidekick
- Falcosidekick API:   http://<host>:2802/api/v1/alerts
"""

import dataclasses
import datetime
import logging
import uuid
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority / severity / status constants
# ---------------------------------------------------------------------------

FALCO_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "emergency": AlertSeverity.CRITICAL,
    "alert": AlertSeverity.CRITICAL,
    "critical": AlertSeverity.CRITICAL,
    "error": AlertSeverity.CRITICAL,
    "warning": AlertSeverity.WARNING,
    "notice": AlertSeverity.INFO,
    "informational": AlertSeverity.INFO,
    "debug": AlertSeverity.LOW,
}

# Rules whose names suggest a resolved / recovery condition
_RESOLVED_RULE_KEYWORDS = frozenset(
    ["resolved", "recovered", "terminated", "stopped", "closed"]
)


def _severity_from_priority(priority: str) -> AlertSeverity:
    """Return a Keep AlertSeverity for a Falco priority string."""
    return FALCO_SEVERITY_MAP.get(priority.lower().strip(), AlertSeverity.INFO)


def _status_from_rule(rule: str) -> AlertStatus:
    """Heuristic: if the rule name contains a recovery keyword, mark RESOLVED."""
    rule_lower = rule.lower()
    if any(kw in rule_lower for kw in _RESOLVED_RULE_KEYWORDS):
        return AlertStatus.RESOLVED
    return AlertStatus.FIRING


def _parse_timestamp(ts: Optional[str]) -> Optional[datetime.datetime]:
    """Parse an ISO-8601 timestamp (with optional nanoseconds) to datetime."""
    if not ts:
        return None
    # Truncate sub-microsecond precision that Python's fromisoformat can't handle
    # e.g. "2026-03-29T10:00:00.123456789Z" → "2026-03-29T10:00:00.123456Z"
    try:
        ts_clean = ts.rstrip("Z")
        dot_pos = ts_clean.rfind(".")
        if dot_pos != -1 and len(ts_clean) - dot_pos > 7:
            ts_clean = ts_clean[: dot_pos + 7]
        return datetime.datetime.fromisoformat(ts_clean).replace(
            tzinfo=datetime.timezone.utc
        )
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class FalcoProviderAuthConfig:
    """
    Authentication / connection configuration for the Falco provider.

    All fields are optional because Falco can be used in pure-push (webhook)
    mode without any outbound connection from Keep.
    """

    sidekick_url: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Falcosidekick base URL (e.g. http://falcosidekick:2801)",
            "hint": "Required for pull mode — leave empty for webhook-only setup",
            "sensitive": False,
        },
    )
    api_token: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "API token for Falcosidekick (if authentication is enabled)",
            "hint": "Set in falcosidekick config as listenerpayload.authentication.bearer",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify TLS certificates when connecting to Falcosidekick",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class FalcoProvider(BaseProvider):
    """
    Pull/Push runtime-security alerts from Falco into Keep.

    Push mode: configure Falco or Falcosidekick to POST JSON events to Keep's
    webhook endpoint.  Keep will parse and store them automatically.

    Pull mode: Keep queries the Falcosidekick HTTP API to fetch recent alerts.
    Requires ``sidekick_url`` in the auth config.
    """

    PROVIDER_DISPLAY_NAME = "Falco"
    PROVIDER_TAGS = ["security", "kubernetes", "runtime", "cloud-native"]
    PROVIDER_CATEGORY = ["Security"]
    WEBHOOK_INSTALLATION_REQUIRED = True

    PROVIDER_SCOPES = [
        ProviderScope(
            name="falcosidekick:read",
            description="Read alerts from Falcosidekick HTTP API (pull mode)",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://github.com/falcosecurity/falcosidekick#outputs",
        ),
    ]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
Configure Falco / Falcosidekick to forward events to Keep:

**Option A — Direct Falco HTTP output** (Falco ≥ 0.31):

Add to your `falco.yaml`:
```yaml
http_output:
  enabled: true
  url: "{keep_webhook_api_url}"
  user_agent: "falcosecurity/falco"
```
Then add the Keep API key header via the `custom_fields` or a proxy.

**Option B — Falcosidekick (recommended)**:

Add to your `falcosidekick/config.yaml`:
```yaml
webhook:
  address: "{keep_webhook_api_url}"
  customheaders: "X-API-KEY:{api_key}"
  minimumpriority: "debug"
```

**Option C — Falcosidekick environment variables**:
```bash
WEBHOOK_ADDRESS={keep_webhook_api_url}
WEBHOOK_CUSTOMHEADERS="X-API-KEY:{api_key}"
WEBHOOK_MINIMUMPRIORITY=debug
```

After configuration, Falco security events will appear in Keep automatically.
"""

    # Falco Priorities: Emergency > Alert > Critical > Error > Warning > Notice > Informational > Debug
    SEVERITY_MAP = FALCO_SEVERITY_MAP

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._session: Optional[requests.Session] = None

    def validate_config(self) -> None:
        self.authentication_config = FalcoProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            token = (self.authentication_config.api_token or "").strip()
            if token:
                self._session.headers["Authorization"] = f"Bearer {token}"
        return self._session

    def _sidekick_request(self, path: str, params: Optional[dict] = None) -> dict:
        """
        Make a GET request to the Falcosidekick API.

        Returns the parsed JSON body or raises requests.HTTPError / ValueError.
        """
        base = (self.authentication_config.sidekick_url or "").rstrip("/")
        if not base:
            raise ValueError(
                "sidekick_url is not configured — pull mode is unavailable"
            )
        url = f"{base}/{path.lstrip('/')}"
        verify = self.authentication_config.verify_ssl
        resp = self._get_session().get(url, params=params, verify=verify, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Pull mode
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Check connectivity to Falcosidekick.  Returns success dict if reachable.
        Webhook-only deployments (no sidekick_url) always return valid.
        """
        sidekick_url = (self.authentication_config.sidekick_url or "").strip()
        if not sidekick_url:
            # Pure webhook mode — nothing to validate
            return {"falcosidekick:read": True}
        try:
            self._sidekick_request("ping")
            return {"falcosidekick:read": True}
        except Exception as exc:
            return {"falcosidekick:read": str(exc)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull recent alerts from the Falcosidekick HTTP API.

        If ``sidekick_url`` is not configured this method returns an empty list
        (alerts arrive via the push/webhook path instead).
        """
        sidekick_url = (self.authentication_config.sidekick_url or "").strip()
        if not sidekick_url:
            logger.debug(
                "falco: sidekick_url not set — skipping pull, using webhook mode"
            )
            return []

        try:
            data = self._sidekick_request("api/v1/alerts")
        except Exception as exc:
            logger.exception("falco: failed to fetch alerts from Falcosidekick: %s", exc)
            return []

        raw_alerts = data if isinstance(data, list) else data.get("alerts", [])
        return [
            alert
            for raw in raw_alerts
            if isinstance(raw, dict)
            for alert in [FalcoProvider._format_alert(raw)]
            if alert is not None
        ]

    # ------------------------------------------------------------------
    # Push mode (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "BaseProvider | None" = None,
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a Falco / Falcosidekick JSON event into a Keep AlertDto.

        Handles two envelope shapes:
        1. Native Falco output (``rule``, ``priority``, ``output``, ``output_fields``, ``time``)
        2. Falcosidekick envelope (may add ``source``, ``tags``, ``hostname`` keys)

        Also handles a batch envelope ``{"events": [...]}`` or ``{"alerts": [...]}``.
        """
        # Batch envelopes
        for batch_key in ("events", "alerts"):
            batch = event.get(batch_key)
            if isinstance(batch, list) and batch:
                return [
                    FalcoProvider._format_alert(item)
                    for item in batch
                    if isinstance(item, dict)
                ]

        rule: str = event.get("rule", "") or event.get("Rule", "") or "Falco Alert"
        priority: str = (
            event.get("priority", "")
            or event.get("Priority", "")
            or "informational"
        )
        output: str = event.get("output", "") or event.get("Output", "") or rule
        output_fields: dict = event.get("output_fields", {}) or event.get("outputFields", {}) or {}
        tags: list = event.get("tags", []) or []
        hostname: str = (
            event.get("hostname", "")
            or output_fields.get("host.hostname", "")
            or output_fields.get("container.id", "")
            or ""
        )

        severity = _severity_from_priority(priority)
        status = _status_from_rule(rule)
        received = _parse_timestamp(event.get("time") or event.get("Time"))

        # Build rich labels from output_fields
        labels: dict[str, str] = {}
        _copy_field(labels, output_fields, "container.id", "container_id")
        _copy_field(labels, output_fields, "container.name", "container_name")
        _copy_field(labels, output_fields, "container.image.repository", "image")
        _copy_field(labels, output_fields, "k8s.pod.name", "pod")
        _copy_field(labels, output_fields, "k8s.ns.name", "namespace")
        _copy_field(labels, output_fields, "k8s.deployment.name", "deployment")
        _copy_field(labels, output_fields, "proc.name", "process")
        _copy_field(labels, output_fields, "proc.cmdline", "cmdline")
        _copy_field(labels, output_fields, "user.name", "user")
        _copy_field(labels, output_fields, "fd.name", "fd")
        _copy_field(labels, output_fields, "evt.type", "syscall")
        if tags:
            labels["tags"] = ",".join(str(t) for t in tags)
        if hostname:
            labels["hostname"] = hostname

        alert = AlertDto(
            id=str(uuid.uuid4()),
            name=rule,
            description=output,
            severity=severity,
            status=status,
            lastReceived=received or datetime.datetime.now(tz=datetime.timezone.utc),
            source=["falco"],
            labels=labels,
        )
        return alert


def _copy_field(
    labels: dict[str, str],
    output_fields: dict,
    src_key: str,
    dst_key: str,
) -> None:
    """Copy a dotted output_field key into the labels dict if present."""
    val = output_fields.get(src_key)
    if val is not None and str(val).strip():
        labels[dst_key] = str(val)


if __name__ == "__main__":
    pass
