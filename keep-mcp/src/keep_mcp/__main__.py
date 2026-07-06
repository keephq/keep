from __future__ import annotations

import logging
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from .client import KeepClient
from .config import load_settings

log = logging.getLogger("keep_mcp")


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not settings.keep_api_key:
        log.error("KEEP_MCP_KEEP_API_KEY is not set; refusing to start")
        sys.exit(2)

    log.info(
        "starting keep-mcp transport=%s keep_api_url=%s",
        settings.transport,
        settings.keep_api_url,
    )

    client = KeepClient(settings.keep_api_url, settings.keep_api_key, settings.http_timeout)
    mcp = FastMCP(
        name="keep",
        instructions=(
            "Read-only access to a Keep AIOps deployment. Use search_alerts and "
            "list_incidents to see what is firing, then get_incident + "
            "list_incident_alerts to drill in. CEL is the query language for "
            "search_alerts — see docs.keephq.dev."
        ),
    )

    @mcp.tool()
    async def search_alerts(cel: str = "", limit: int = 25, offset: int = 0) -> dict[str, Any]:
        """Query Keep alerts. `cel` is a CEL expression like `severity == "critical"`; empty returns most recent."""
        return await client.query_alerts(cel=cel, limit=max(1, min(limit, 1000)), offset=offset)

    @mcp.tool()
    async def list_incidents(
        status: list[str] | None = None,
        severity: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        cel: str | None = None,
    ) -> dict[str, Any]:
        """List Keep incidents. Defaults to active incidents (firing + acknowledged) when status is omitted."""
        if status is None:
            status = ["firing", "acknowledged"]
        return await client.list_incidents(
            status=status,
            severity=severity,
            limit=max(1, min(limit, 500)),
            offset=offset,
            cel=cel,
        )

    @mcp.tool()
    async def get_incident(incident_id: str) -> dict[str, Any]:
        """Fetch a single incident by UUID."""
        return await client.get_incident(incident_id)

    @mcp.tool()
    async def list_incident_alerts(
        incident_id: str, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        """List alerts linked to an incident."""
        return await client.get_incident_alerts(
            incident_id, limit=max(1, min(limit, 200)), offset=offset
        )

    @mcp.tool()
    async def get_topology(service: str | None = None) -> list[dict[str, Any]]:
        """Return the service dependency graph, optionally scoped to one service."""
        return await client.get_topology(service=service)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(_: Request) -> JSONResponse:
        try:
            resp = await client.get("/healthcheck")
            ready = resp.status_code < 500
        except httpx.HTTPError:
            ready = False
        return JSONResponse(
            {"ready": ready, "keep_api_url": settings.keep_api_url},
            status_code=200 if ready else 503,
        )

    if settings.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = settings.http_host
        mcp.settings.port = settings.http_port
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
