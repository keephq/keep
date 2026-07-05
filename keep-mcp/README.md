# keep-mcp

Model Context Protocol (MCP) server for [Keep](https://github.com/keephq/keep) — exposes Keep's alerts, incidents, and topology to LLM agents as MCP tools and resources.

Runs as an independent container alongside `keep-backend` and `keep-frontend`. Talks to the Keep REST API via `X-API-KEY`; never touches Keep's database or secret manager directly.

## v0.1 scope (read-only)

**Tools**

- `search_alerts(cel, limit, offset)` — query alerts with a CEL expression (same expression language the Keep UI uses).
- `list_incidents(status, severity, limit, offset)` — list incidents, filterable by status (`firing`, `acknowledged`, `resolved`, `merged`, `deleted`) and severity.
- `get_incident_with_alerts(incident_id, alerts_limit)` — fetch an incident and its linked alerts in one call.
- `get_topology(service)` — service dependency graph, optionally scoped to one service.

**Resources**

- `keep://alerts` — recent alerts
- `keep://incidents` — active incidents
- `keep://topology` — full topology

Write tools (`enrich_alert`, `create_incident`, `run_workflow`, …) and LGTM passthrough (`loki_query_range`, `mimir_query_range`, `tempo_search_traces`) are planned for v0.2 / v0.3. See `plan.md` in the parent worktree for the full roadmap.

## Configuration

Every setting is an environment variable. Prefix `KEEP_MCP_`.

| Variable | Default | Description |
|---|---|---|
| `KEEP_MCP_KEEP_API_URL` | `http://keep-backend:8080` | Base URL of the Keep REST API |
| `KEEP_MCP_KEEP_API_KEY` | *(required)* | API key used on every request (`X-API-KEY`) |
| `KEEP_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `KEEP_MCP_HTTP_HOST` | `0.0.0.0` | Bind host for `streamable-http` |
| `KEEP_MCP_HTTP_PORT` | `8090` | Bind port for `streamable-http` |
| `KEEP_MCP_HTTP_TIMEOUT` | `30` | httpx timeout for calls to `keep-backend` |
| `KEEP_MCP_LOG_LEVEL` | `INFO` | Root log level |

## Running locally (stdio, for Claude Desktop / Copilot CLI / Cursor)

```bash
poetry install
KEEP_MCP_KEEP_API_URL=http://localhost:8080 \
KEEP_MCP_KEEP_API_KEY=your-key \
poetry run keep-mcp
```

Example client config (`~/.copilot/mcp.json`):

```json
{
  "servers": {
    "keep": {
      "command": "poetry",
      "args": ["run", "keep-mcp"],
      "cwd": "/path/to/keep/keep-mcp",
      "env": {
        "KEEP_MCP_KEEP_API_URL": "http://localhost:8080",
        "KEEP_MCP_KEEP_API_KEY": "your-key"
      }
    }
  }
}
```

## Running in Docker (streamable-http)

Ships as `keep-mcp` in the repo's `docker-compose.yml`. Enable it with:

```bash
KEEP_MCP_KEEP_API_KEY=your-key docker compose up keep-mcp
```

Health checks:

- `GET http://localhost:8090/healthz` — process liveness
- `GET http://localhost:8090/readyz` — verifies `keep-backend` reachable

## Architecture

Thin adapter. All auth/RBAC/tenancy stay in `keep-backend`. This container is a stateless HTTP client — safe to scale horizontally and safe to restart at will.
