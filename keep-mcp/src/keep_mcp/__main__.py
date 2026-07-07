"""keep-mcp — Model Context Protocol server for Keep."""

import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.responses import PlainTextResponse

API_URL = os.environ.get("KEEP_MCP_KEEP_API_URL", "http://keep-backend:8080").rstrip("/")
API_KEY = os.environ.get("KEEP_MCP_KEEP_API_KEY", "")
TRANSPORT = os.environ.get("KEEP_MCP_TRANSPORT", "stdio")
HTTP_HOST = os.environ.get("KEEP_MCP_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("KEEP_MCP_HTTP_PORT", "8090"))

http = httpx.AsyncClient(
    base_url=API_URL,
    timeout=30.0,
    headers={"X-API-KEY": API_KEY, "User-Agent": "keep-mcp/0.1"},
)

mcp = FastMCP(
    name="keep",
    instructions=(
        "Read-only access to a Keep AIOps deployment. Use search_alerts and "
        "list_incidents to see what is firing, then get_incident + "
        "list_incident_alerts to drill in. CEL is the query language for "
        "search_alerts — see docs.keephq.dev."
    ),
)


async def _json(method: str, path: str, **kw):
    r = await http.request(method, path, **kw)
    r.raise_for_status()
    return r.json() if r.content else None


@mcp.tool()
async def search_alerts(cel: str = "", limit: int = 25, offset: int = 0) -> dict:
    """Query Keep alerts. `cel` is a CEL filter like `severity == "critical"`; empty returns most recent."""
    return await _json("POST", "/alerts/query", json={"cel": cel, "limit": limit, "offset": offset})


@mcp.tool()
async def list_incidents(
    status: list[str] | None = None,
    severity: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
    cel: str | None = None,
) -> dict:
    """List Keep incidents. status ⊆ {firing, resolved, acknowledged, merged, deleted}; severity ⊆ {critical, high, warning, info, low}."""
    params: list[tuple[str, str | int]] = [("limit", limit), ("offset", offset)]
    params += [("status", s) for s in status or []]
    params += [("severity", s) for s in severity or []]
    if cel:
        params.append(("cel", cel))
    return await _json("GET", "/incidents", params=params)


@mcp.tool()
async def get_incident(incident_id: str) -> dict:
    return await _json("GET", f"/incidents/{incident_id}")


@mcp.tool()
async def list_incident_alerts(incident_id: str, limit: int = 25, offset: int = 0) -> dict:
    return await _json(
        "GET", f"/incidents/{incident_id}/alerts", params={"limit": limit, "offset": offset}
    )


@mcp.tool()
async def get_topology(service: str | None = None) -> list[dict]:
    return await _json("GET", "/topology", params={"service": service} if service else None)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_):
    return PlainTextResponse("ok")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not API_KEY:
        logging.error("KEEP_MCP_KEEP_API_KEY is not set; refusing to start")
        sys.exit(2)
    logging.info("starting keep-mcp transport=%s keep_api_url=%s", TRANSPORT, API_URL)
    if TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = HTTP_HOST
        mcp.settings.port = HTTP_PORT
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
