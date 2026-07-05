from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from .client import KeepAPIError, KeepClient
from .config import Settings

logger = logging.getLogger(__name__)

INCIDENT_STATUSES = ["firing", "resolved", "acknowledged", "merged", "deleted"]
INCIDENT_SEVERITIES = ["critical", "high", "warning", "info", "low"]


def build_server(settings: Settings) -> FastMCP:
    """Construct a FastMCP server wired to a Keep API client."""
    client = KeepClient(
        base_url=settings.keep_api_url,
        api_key=settings.keep_api_key,
        timeout=settings.http_timeout,
    )
    mcp = FastMCP(
        name="keep",
        instructions=(
            "Read-only access to a Keep AIOps deployment. Use search_alerts and "
            "list_incidents to discover what is currently firing, then "
            "get_incident_with_alerts to drill into a specific incident. "
            "CEL is the query language for search_alerts — see docs.keephq.dev."
        ),
    )

    # --- tools ---

    @mcp.tool()
    async def search_alerts(
        cel: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query Keep alerts with an optional CEL expression.

        Args:
            cel: CEL filter, e.g. `severity == "critical" && status == "firing"`.
                 Empty string returns the most recent alerts.
            limit: Max alerts to return (1–1000).
            offset: Pagination offset.

        Returns a dict with `count`, `limit`, `offset`, and `results` (alert DTOs).
        """
        limit = max(1, min(limit, 1000))
        return await client.query_alerts(cel=cel, limit=limit, offset=offset)

    @mcp.tool()
    async def list_incidents(
        status: list[str] | None = None,
        severity: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        cel: str | None = None,
    ) -> dict[str, Any]:
        """List Keep incidents, filterable by status and severity.

        Args:
            status: Subset of {firing, resolved, acknowledged, merged, deleted}.
                    Defaults to active incidents (firing + acknowledged) when omitted.
            severity: Subset of {critical, high, warning, info, low}.
            limit: Max incidents to return (1–500).
            offset: Pagination offset.
            cel: Optional CEL filter applied server-side.
        """
        limit = max(1, min(limit, 500))
        if status is None:
            status = ["firing", "acknowledged"]
        _validate_subset("status", status, INCIDENT_STATUSES)
        if severity:
            _validate_subset("severity", severity, INCIDENT_SEVERITIES)
        return await client.list_incidents(
            status=status, severity=severity, limit=limit, offset=offset, cel=cel
        )

    @mcp.tool()
    async def get_incident_with_alerts(
        incident_id: str,
        alerts_limit: int = 25,
    ) -> dict[str, Any]:
        """Fetch an incident by id together with its linked alerts.

        Args:
            incident_id: UUID of the incident.
            alerts_limit: Max alerts to include (1–200).
        """
        alerts_limit = max(1, min(alerts_limit, 200))
        incident = await client.get_incident(incident_id)
        alerts = await client.get_incident_alerts(incident_id, limit=alerts_limit)
        return {"incident": incident, "alerts": alerts}

    @mcp.tool()
    async def get_topology(service: str | None = None) -> list[dict[str, Any]]:
        """Return the service dependency graph, optionally scoped to one service."""
        return await client.get_topology(service=service)

    # --- resources ---

    @mcp.resource("keep://alerts")
    async def resource_alerts() -> str:
        data = await client.query_alerts(limit=50)
        return json.dumps(data, default=str, indent=2)

    @mcp.resource("keep://incidents")
    async def resource_incidents() -> str:
        data = await client.list_incidents(
            status=["firing", "acknowledged"], limit=50
        )
        return json.dumps(data, default=str, indent=2)

    @mcp.resource("keep://topology")
    async def resource_topology() -> str:
        data = await client.get_topology()
        return json.dumps(data, default=str, indent=2)

    # --- health endpoints (streamable-http mode only) ---

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(_request: Request) -> JSONResponse:
        ok = await client.ping()
        status = 200 if ok else 503
        return JSONResponse(
            {"ready": ok, "keep_api_url": settings.keep_api_url},
            status_code=status,
        )

    return mcp


def _validate_subset(name: str, values: list[str], allowed: list[str]) -> None:
    invalid = [v for v in values if v not in allowed]
    if invalid:
        raise KeepAPIError(
            422,
            f"invalid {name} values {invalid!r}; allowed={allowed}",
            f"validation:{name}",
        )
