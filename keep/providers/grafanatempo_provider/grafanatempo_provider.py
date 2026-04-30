"""
GrafanaTempoProvider is a class that allows you to query traces from Grafana Tempo
and surface high-latency or error traces as Keep alerts.

Grafana Tempo is a distributed tracing backend that is fully compatible with Jaeger,
Zipkin, OpenTelemetry, and Grafana's native TraceQL query language.
"""

import dataclasses
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class GrafanaTempoProviderAuthConfig:
    """
    Grafana Tempo authentication configuration.
    Works with self-hosted Tempo (optionally behind Grafana) and Grafana Cloud Tempo.
    """

    host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Tempo host URL",
            "hint": "e.g. https://tempo.example.com or https://tempo-prod-01-prod-us-east-0.grafana.net",
            "validation": "any_http_url",
        }
    )
    token: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "API token or Basic Auth password (for Grafana Cloud use your API key)",
            "hint": "Leave blank for unauthenticated / network-protected Tempo instances",
            "sensitive": True,
        },
        default=None,
    )
    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Username for Basic Auth (Grafana Cloud: your numeric instance ID)",
            "hint": "Only required when using HTTP Basic Auth",
        },
        default=None,
    )
    error_rate_threshold_pct: float = dataclasses.field(
        metadata={
            "required": False,
            "description": "Minimum root-span error rate (%) to surface as a Critical alert",
            "hint": "Default: 5.0 — set to 0 to pull all erroring traces",
        },
        default=5.0,
    )
    latency_threshold_ms: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Root-span P99 duration (ms) above which a trace is surfaced as a High alert",
            "hint": "Default: 2000 (2 seconds)",
        },
        default=2000,
    )


class GrafanaTempoProvider(BaseProvider):
    """Query Grafana Tempo for slow or erroring traces and surface them as Keep alerts."""

    PROVIDER_DISPLAY_NAME = "Grafana Tempo"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_TAGS = ["alert", "tracing", "observability"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="tempo_read",
            description="Can query traces and metadata from Tempo",
            mandatory=True,
            alias="Tempo Read",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = GrafanaTempoProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        auth = self.authentication_config
        if auth.username and auth.token:
            import base64
            creds = base64.b64encode(f"{auth.username}:{auth.token}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        elif auth.token:
            headers["Authorization"] = f"Bearer {auth.token}"
        return headers

    def _url(self, path: str) -> str:
        host = str(self.authentication_config.host).rstrip("/")
        return f"{host}{path}"

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating Grafana Tempo scopes")
        url = self._url("/api/echo")
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.ok:
                return {"tempo_read": True}
            # Try the status endpoint as a fallback
            url2 = self._url("/ready")
            resp2 = requests.get(url2, headers=self._get_headers(), timeout=10)
            if resp2.ok or resp2.status_code == 200:
                return {"tempo_read": True}
            return {"tempo_read": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"tempo_read": str(e)}

    # ------------------------------------------------------------------
    # Alert pulling via TraceQL search
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Use the Tempo search API (TraceQL) to find traces with errors or high latency
        and surface them as Keep alerts.
        """
        self.logger.info("Querying Grafana Tempo for error/high-latency traces")
        alerts = []

        # Pull erroring root spans
        alerts.extend(self._query_error_traces())
        # Pull slow root spans
        alerts.extend(self._query_slow_traces())

        # Deduplicate by trace ID
        seen = set()
        unique = []
        for a in alerts:
            if a.id not in seen:
                seen.add(a.id)
                unique.append(a)

        self.logger.info(f"Found {len(unique)} traces to surface as alerts")
        return unique

    def _query_error_traces(self) -> list[AlertDto]:
        """Search for root spans with status=error."""
        query = '{status=error && rootSpan=true}'
        return self._run_traceql_query(query, AlertSeverity.CRITICAL, "Error trace")

    def _query_slow_traces(self) -> list[AlertDto]:
        """Search for slow root spans above the configured latency threshold."""
        threshold_ns = self.authentication_config.latency_threshold_ms * 1_000_000
        query = f'{{rootSpan=true && duration>{threshold_ns}ns}}'
        return self._run_traceql_query(query, AlertSeverity.HIGH, "Slow trace")

    def _run_traceql_query(
        self, query: str, severity: AlertSeverity, label: str
    ) -> list[AlertDto]:
        url = self._url("/api/search")
        params = {"q": query, "limit": 50}
        try:
            resp = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            self.logger.warning(
                f"Tempo search query failed: {label}",
                extra={"error": str(e), "query": query},
            )
            return []

        traces = resp.json().get("traces", [])
        alerts = []
        for trace in traces:
            alerts.append(self._trace_to_alert(trace, severity, label))
        return alerts

    def _trace_to_alert(self, trace: dict, severity: AlertSeverity, label: str) -> AlertDto:
        trace_id = trace.get("traceID", "")
        root_service = trace.get("rootServiceName", "unknown")
        root_trace_name = trace.get("rootTraceName", "")
        duration_ms = trace.get("durationMs", 0)
        start_time_unix_ns = trace.get("startTimeUnixNano", 0)

        if start_time_unix_ns:
            try:
                ts = datetime.fromtimestamp(int(start_time_unix_ns) / 1e9, tz=timezone.utc)
                last_received = ts.isoformat()
            except (ValueError, OverflowError):
                last_received = datetime.now(timezone.utc).isoformat()
        else:
            last_received = datetime.now(timezone.utc).isoformat()

        status = AlertStatus.FIRING if severity == AlertSeverity.CRITICAL else AlertStatus.FIRING
        name = f"{label}: {root_service} / {root_trace_name}" if root_trace_name else f"{label}: {root_service}"
        description = (
            f"Trace ID: {trace_id} | Service: {root_service} | Duration: {duration_ms}ms"
        )

        host = str(self.authentication_config.host).rstrip("/")
        trace_url = f"{host}/explore?left=%7B%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%7D%2C%22queryType%22%3A%22traceId%22%2C%22query%22%3A%22{trace_id}%22%7D%5D%7D"

        return AlertDto(
            id=trace_id,
            fingerprint=trace_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            url=trace_url,
            service=root_service,
            durationMs=duration_ms,
            source=["grafanatempo"],
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = ProviderConfig(
        description="Grafana Tempo Provider",
        authentication={
            "host": os.environ.get("TEMPO_HOST", "http://localhost:3200"),
            "token": os.environ.get("TEMPO_TOKEN"),
        },
    )

    provider = GrafanaTempoProvider(context_manager, "grafanatempo", config)
    print(provider.validate_scopes())
    print(provider._get_alerts())
