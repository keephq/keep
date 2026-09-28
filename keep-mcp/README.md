# keep-mcp

Read-only Model Context Protocol server for [Keep](https://github.com/keephq/keep). Sidecar container next to `keep-backend` / `keep-frontend`, thin proxy over the Keep REST API (`X-API-KEY`).

## Tools

`search_alerts` · `list_incidents` · `get_incident` · `list_incident_alerts` · `get_topology`

Query language for `search_alerts` is CEL — see [docs.keephq.dev](https://docs.keephq.dev).

## Run

```bash
KEEP_MCP_KEEP_API_KEY=<your-key> docker compose --profile mcp up keep-mcp
curl http://localhost:8090/healthz
```

Env: `KEEP_MCP_KEEP_API_URL` (default `http://keep-backend:8080`), `KEEP_MCP_KEEP_API_KEY` (required), `KEEP_MCP_TRANSPORT` (`stdio` | `streamable-http`, default `stdio`), `KEEP_MCP_HTTP_HOST`/`PORT` (streamable-http only).

## Security

The `streamable-http` endpoint is unauthenticated in v0.1 and holds a Keep API key, so
anything that can reach the port gets read access to your alerts, incidents and topology.
Run it on the compose network or a trusted local host, not on a public interface.
Endpoint auth arrives in v0.2 alongside OAuth.

Write tools and LGTM passthrough land in v0.2/v0.3.
