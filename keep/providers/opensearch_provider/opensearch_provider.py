"""
OpenSearchProvider integrates OpenSearch with Keep.

OpenSearch is an open-source fork of Elasticsearch maintained by AWS. It provides
a RESTful JSON API compatible with Elasticsearch 7.x. This provider uses the HTTP
REST API directly (no external SDK required).

Supported modes:
  - Query mode: run DSL queries or SQL queries against an OpenSearch index
  - Alert query: poll the OpenSearch Alerting plugin (/_plugins/_alerting/alerts)
  - Webhook (push): receive alerts from OpenSearch Alerting notifications

Authentication:
  - username + password (HTTP Basic Auth)
  - API key (via Authorization: ApiKey header)
  - AWS signature (not yet supported — use VPC endpoint or API key)

References:
  https://opensearch.org/docs/latest/api-reference/
  https://opensearch.org/docs/latest/observing-your-data/alerting/api/
"""

import base64
import dataclasses
import datetime
import json
import logging
from typing import Any, Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class OpenSearchProviderAuthConfig:
    """
    OpenSearch authentication configuration.

    Provide either username+password (HTTP Basic Auth) or an api_key.
    At least one authentication method must be set.
    """

    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenSearch cluster URL",
            "hint": "https://opensearch.example.com:9200",
            "validation": "any_http_url",
        }
    )
    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "OpenSearch username (Basic Auth)",
            "hint": "admin",
            "sensitive": False,
        },
        default=None,
    )
    password: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "OpenSearch password (Basic Auth)",
            "sensitive": True,
        },
        default=None,
    )
    api_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "OpenSearch API key (base64-encoded id:api_key)",
            "hint": "Obtained from POST /_plugins/_security/api/v1/api_key",
            "sensitive": True,
        },
        default=None,
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class OpenSearchProvider(BaseProvider):
    """
    Query OpenSearch indices and receive alerts from OpenSearch Alerting.

    Pull mode: polls /_plugins/_alerting/alerts for active monitors.
    Query mode: executes DSL or SQL queries against any index.
    Push mode: receives JSON payloads from OpenSearch Alerting webhook channels.
    """

    PROVIDER_DISPLAY_NAME = "OpenSearch"
    PROVIDER_TAGS = ["logs", "monitoring", "search"]
    PROVIDER_CATEGORY = ["Monitoring", "Database"]
    FINGERPRINT_FIELDS = ["id"]

    # Webhook push mode documentation
    webhook_description = "Receive alerts from OpenSearch Alerting via webhook"
    webhook_template = ""
    webhook_markdown = """
To receive OpenSearch Alerting notifications in Keep:

1. In OpenSearch Dashboards, go to **Alerting** → **Notification channels**.
2. Click **Create channel**.
3. Choose **Custom webhook** as the channel type.
4. Set the **URL** to `{keep_webhook_api_url}`.
5. Add a custom header `Authorization: Bearer {api_key}` (or use HTTP Basic Auth).
6. Set the **Request body** to:
```json
{{
  "id": "{{ctx.monitor.id}}",
  "name": "{{ctx.monitor.name}}",
  "trigger_name": "{{ctx.trigger.name}}",
  "severity": "{{ctx.trigger.severity}}",
  "state": "{{ctx.results[0].hits.total.value}}",
  "message": "{{ctx.results[0]._source.message}}",
  "index": "{{ctx.monitor_name}}"
}}
```
7. Click **Send test message** to verify, then **Create**.
8. Assign this channel to a monitor trigger.
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="cluster_read",
            description="Read access to OpenSearch cluster info and indices",
            mandatory=True,
            alias="Cluster Read",
            documentation_url="https://opensearch.org/docs/latest/api-reference/",
        ),
        ProviderScope(
            name="alerting_read",
            description="Read access to OpenSearch Alerting plugin",
            mandatory=False,
            alias="Alerting Read",
            documentation_url="https://opensearch.org/docs/latest/observing-your-data/alerting/api/",
        ),
    ]

    # OpenSearch alert state → Keep AlertStatus
    STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "completed": AlertStatus.RESOLVED,
        "deleted": AlertStatus.RESOLVED,
        "error": AlertStatus.FIRING,
    }

    # OpenSearch Alerting severity 1-5 → Keep AlertSeverity
    SEVERITY_MAP = {
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.INFO,
        "5": AlertSeverity.LOW,
        # Named variants (from OpenSearch Alerting plugin)
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
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
        """Validate and parse OpenSearch authentication config."""
        self.authentication_config = OpenSearchProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.username
            and not self.authentication_config.password
            and not self.authentication_config.api_key
        ):
            raise ValueError(
                "OpenSearch provider requires either username+password or api_key authentication."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_auth_headers(self) -> dict:
        """Return HTTP auth headers for the configured authentication method."""
        if self.authentication_config.api_key:
            return {"Authorization": f"ApiKey {self.authentication_config.api_key}"}
        elif self.authentication_config.username and self.authentication_config.password:
            credentials = base64.b64encode(
                f"{self.authentication_config.username}:{self.authentication_config.password}".encode()
            ).decode()
            return {"Authorization": f"Basic {credentials}"}
        else:
            return {}

    def _build_url(self, path: str) -> str:
        """Build an absolute URL from a relative API path."""
        base = str(self.authentication_config.url).rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def _api_get(self, path: str, params: Optional[dict] = None) -> dict:
        """Perform an authenticated GET against the OpenSearch API."""
        url = self._build_url(path)
        headers = {
            "Content-Type": "application/json",
            **self._get_auth_headers(),
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _api_post(self, path: str, body: dict, params: Optional[dict] = None) -> dict:
        """Perform an authenticated POST against the OpenSearch API."""
        url = self._build_url(path)
        headers = {
            "Content-Type": "application/json",
            **self._get_auth_headers(),
        }
        response = requests.post(
            url,
            headers=headers,
            json=body,
            params=params,
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # validate_scopes
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict:
        """
        Verify connectivity to the OpenSearch cluster using GET /.

        Also checks if the Alerting plugin is available.
        """
        result = {}
        # Basic connectivity + auth check
        try:
            info = self._api_get("/")
            cluster_name = info.get("cluster_name", "unknown")
            self.logger.info("Connected to OpenSearch cluster: %s", cluster_name)
            result["cluster_read"] = True
        except requests.exceptions.HTTPError as exc:
            self.logger.error(
                "OpenSearch connectivity check failed",
                extra={"status_code": exc.response.status_code if exc.response else None},
            )
            result["cluster_read"] = str(exc)
        except Exception as exc:
            self.logger.error("OpenSearch connectivity failed", extra={"error": str(exc)})
            result["cluster_read"] = str(exc)

        # Alerting plugin check (optional)
        try:
            self._api_get("/_plugins/_alerting/alerts", params={"size": 0})
            result["alerting_read"] = True
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                result["alerting_read"] = "Insufficient permissions for Alerting API"
            elif exc.response is not None and exc.response.status_code == 404:
                result["alerting_read"] = "Alerting plugin not installed"
            else:
                result["alerting_read"] = str(exc)
        except Exception as exc:
            result["alerting_read"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Pull mode: query Alerting plugin
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch active alerts from the OpenSearch Alerting plugin.
        Uses GET /_plugins/_alerting/alerts.
        """
        self.logger.info("Fetching alerts from OpenSearch Alerting plugin")
        try:
            data = self._api_get(
                "/_plugins/_alerting/alerts",
                params={"size": 200, "sortField": "start_time", "sortOrder": "desc"},
            )
        except Exception as exc:
            self.logger.error(
                "Failed to fetch OpenSearch alerts", extra={"error": str(exc)}
            )
            raise

        alerts = data.get("alerts", [])
        self.logger.info("Retrieved %d alerts from OpenSearch Alerting", len(alerts))
        return [self._alert_to_dto(alert) for alert in alerts]

    def _alert_to_dto(self, alert: dict) -> AlertDto:
        """Convert an OpenSearch Alerting alert dict to AlertDto."""
        state = (alert.get("state") or "active").lower()
        severity = (alert.get("severity") or "3").lower()

        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)
        alert_severity = self.SEVERITY_MAP.get(severity, AlertSeverity.WARNING)

        alert_id = alert.get("id", "")
        monitor_name = alert.get("monitor_name", "Unknown Monitor")
        trigger_name = alert.get("trigger_name", "")
        error_message = alert.get("error_message", "")
        start_time = alert.get("start_time", "")
        end_time = alert.get("end_time", "")
        monitor_id = alert.get("monitor_id", "")
        trigger_id = alert.get("trigger_id", "")

        name = f"{monitor_name} / {trigger_name}" if trigger_name else monitor_name
        description = error_message or f"Alert triggered by monitor '{monitor_name}'"

        # Use end_time if resolved, start_time otherwise
        last_received = end_time or start_time or datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            status=status,
            severity=alert_severity,
            lastReceived=last_received,
            source=["opensearch"],
            service=monitor_name,
            labels={
                "monitor_id": monitor_id,
                "monitor_name": monitor_name,
                "trigger_id": trigger_id,
                "trigger_name": trigger_name,
                "state": state,
                "severity": severity,
            },
        )

    # ------------------------------------------------------------------
    # Query mode
    # ------------------------------------------------------------------

    def _query(self, query: Any, index: str = None, **kwargs) -> list[dict]:
        """
        Query an OpenSearch index using DSL or SQL.

        Args:
            query: A DSL dict (for index search) or SQL string (for SQL API)
            index:  Target index name. If None, uses the SQL API.

        Returns:
            List of hit dicts (DSL) or row dicts (SQL)
        """
        if index:
            return self._run_dsl_query(query=query, index=index)
        else:
            return self._run_sql_query(query=str(query))

    def _run_dsl_query(self, query: Any, index: str) -> list[dict]:
        """Run a DSL search query against an OpenSearch index."""
        if isinstance(query, str):
            try:
                query = json.loads(query)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid DSL query JSON: {query}")

        self.logger.info("Running DSL query on index '%s'", index)
        response = self._api_post(f"/{index}/_search", body=query)
        hits = response.get("hits", {}).get("hits", [])
        self.logger.debug("DSL query returned %d hits", len(hits))
        return hits

    def _run_sql_query(self, query: str) -> list[dict]:
        """Run an SQL query via the OpenSearch SQL plugin."""
        self.logger.info("Running SQL query via OpenSearch SQL plugin")
        response = self._api_post(
            "/_plugins/_sql",
            body={"query": query},
            params={"format": "json"},
        )
        columns = [col["name"] for col in response.get("schema", [])]
        rows = response.get("datarows", [])
        result = []
        for row in rows:
            result.append(dict(zip(columns, row)))
        self.logger.debug("SQL query returned %d rows", len(result))
        return result

    # ------------------------------------------------------------------
    # Push mode: _format_alert (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "OpenSearchProvider" = None
    ) -> AlertDto:
        """
        Format an OpenSearch Alerting webhook payload into an AlertDto.

        OpenSearch Alerting can send custom webhook bodies using Mustache templates.
        We support a flexible schema to handle various template formats.
        """
        # State / severity
        state = (
            event.get("state")
            or event.get("status")
            or event.get("alert_state")
            or "active"
        ).lower()
        severity_raw = str(
            event.get("severity")
            or event.get("alert_severity")
            or "3"
        ).lower()

        status = OpenSearchProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        severity = OpenSearchProvider.SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING)

        # Identity
        alert_id = (
            event.get("id")
            or event.get("alert_id")
            or event.get("monitor_id", "opensearch-unknown")
        )
        monitor_name = (
            event.get("name")
            or event.get("monitor_name")
            or event.get("monitor", "Unknown Monitor")
        )
        trigger_name = event.get("trigger_name") or event.get("trigger") or ""
        message = event.get("message") or event.get("error_message") or ""
        index = event.get("index") or event.get("monitor_name") or ""
        timestamp = event.get("timestamp") or event.get("start_time") or ""

        name = f"{monitor_name} / {trigger_name}" if trigger_name else monitor_name
        description = message or f"Alert from OpenSearch monitor '{monitor_name}'"

        return AlertDto(
            id=str(alert_id),
            name=name,
            description=description,
            status=status,
            severity=severity,
            lastReceived=timestamp or datetime.datetime.utcnow().isoformat(),
            source=["opensearch"],
            service=monitor_name,
            labels={
                "state": state,
                "severity": severity_raw,
                "trigger_name": trigger_name,
                "index": index,
                "monitor_name": monitor_name,
            },
        )
