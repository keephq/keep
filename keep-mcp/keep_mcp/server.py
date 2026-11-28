import asyncio
import hashlib
import logging
from typing import Any

from keep_mcp import __version__
from keep_mcp.client import KeepAPIError, KeepClient, seg
from keep_mcp.config import Settings
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("keep_mcp")

INCIDENT_STATUSES = ("firing", "resolved", "acknowledged", "merged", "deleted")
ALERT_STATUSES = (
    "firing",
    "resolved",
    "acknowledged",
    "suppressed",
    "pending",
    "maintenance",
)
CHANGEABLE_INCIDENT_STATUSES = ("firing", "resolved", "acknowledged")
WRITE_HINTS = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
RUN_HINTS = ToolAnnotations(readOnlyHint=False, destructiveHint=True)


def _status_cel(statuses: list[str]) -> str:
    # backend /incidents ignores its `status` param, so filter via CEL
    return " || ".join(f'status == "{s}"' for s in statuses)


MAX_LIMIT = 200


def _clamp(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def _request_api_key(ctx: Context | None) -> str | None:
    """API key supplied by an HTTP MCP client (overrides the server default)."""
    if ctx is None:
        return None
    try:
        request = ctx.request_context.request
    except (ValueError, AttributeError):
        return None
    headers = getattr(request, "headers", None)
    return headers.get("x-api-key") if headers is not None else None


def create_server(
    settings: Settings | None = None, client: KeepClient | None = None
) -> FastMCP:
    settings = settings or Settings.from_env()
    # Remote HTTP callers must authenticate with their own key; the env key is
    # only a default for single-user stdio.
    default_key = settings.keep_api_key if settings.transport == "stdio" else None
    keep = client or KeepClient(
        settings.keep_api_url,
        default_key,
        settings.timeout,
        require_key=settings.transport != "stdio",
    )

    mcp = FastMCP(
        "keep",
        instructions=(
            "Read-only access to a Keep AIOps deployment: alerts, incidents and "
            "service topology. Authorization is enforced by Keep using the API key."
        ),
        host=settings.host,
        port=settings.port,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.allowed_hosts),
            allowed_origins=list(settings.allowed_origins),
        ),
    )

    @mcp.tool()
    async def search_alerts(
        cel: str = "",
        limit: int = 50,
        offset: int = 0,
        ctx: Context = None,
    ) -> Any:
        """Search alerts with a CEL expression, e.g. `severity == "critical" && status == "firing"`.
        An empty expression returns the latest alerts."""
        body = {
            "cel": cel,
            "limit": _clamp(limit),
            "offset": max(0, offset),
            "sort_by": None,
            "sort_dir": None,
            "sort_options": None,
        }
        return await keep.post(
            "/alerts/query", json=body, api_key=_request_api_key(ctx)
        )

    @mcp.tool()
    async def list_incidents(
        status: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        ctx: Context = None,
    ) -> Any:
        """List incidents, optionally filtered by status
        (firing, resolved, acknowledged, merged, deleted)."""
        if status:
            invalid = [s for s in status if s not in INCIDENT_STATUSES]
            if invalid:
                raise ValueError(
                    f"Invalid status {invalid}; expected any of {list(INCIDENT_STATUSES)}"
                )
        return await keep.get(
            "/incidents",
            params={
                "cel": _status_cel(status) if status else None,
                "limit": _clamp(limit),
                "offset": max(0, offset),
            },
            api_key=_request_api_key(ctx),
        )

    @mcp.tool()
    async def get_incident_with_alerts(
        incident_id: str,
        alerts_limit: int = 50,
        alerts_offset: int = 0,
        ctx: Context = None,
    ) -> Any:
        """Get an incident together with its linked alerts (paginated: the alerts
        result has `count`; use alerts_offset to fetch further pages)."""
        key = _request_api_key(ctx)
        incident = await keep.get(f"/incidents/{seg(incident_id)}", api_key=key)
        alerts = await keep.get(
            f"/incidents/{seg(incident_id)}/alerts",
            params={"limit": _clamp(alerts_limit), "offset": max(0, alerts_offset)},
            api_key=key,
        )
        return {"incident": incident, "alerts": alerts}

    @mcp.tool()
    async def get_topology(
        services: str | None = None,
        environment: str | None = None,
        provider_ids: str | None = None,
        ctx: Context = None,
    ) -> Any:
        """Get the service topology (services and their dependencies).
        Filters are optional; `services` and `provider_ids` are comma-separated."""
        return await keep.get(
            "/topology",
            params={
                "services": services,
                "environment": environment,
                "provider_ids": provider_ids,
            },
            api_key=_request_api_key(ctx),
        )

    @mcp.tool()
    async def get_alert_history(fingerprint: str, ctx: Context = None) -> Any:
        """Get the history of an alert by its fingerprint."""
        return await keep.get(
            f"/alerts/{seg(fingerprint)}/history", api_key=_request_api_key(ctx)
        )

    @mcp.tool()
    async def get_alert_status_summary(ctx: Context = None) -> Any:
        """Count alerts per status (firing, acknowledged, resolved, ...)."""
        key = _request_api_key(ctx)

        async def count(status: str) -> int:
            body = {
                "cel": f'status == "{status}"',
                "limit": 1,
                "offset": 0,
                "sort_by": None,
                "sort_dir": None,
                "sort_options": None,
            }
            res = await keep.post("/alerts/query", json=body, api_key=key)
            return res.get("count", 0)

        counts = await asyncio.gather(*(count(s) for s in ALERT_STATUSES))
        return dict(zip(ALERT_STATUSES, counts))

    @mcp.tool()
    async def get_incident_status_summary(ctx: Context = None) -> Any:
        """Count incidents per status (firing, acknowledged, resolved, merged, deleted)."""
        key = _request_api_key(ctx)

        async def count(status: str) -> int:
            res = await keep.get(
                "/incidents",
                params={"cel": _status_cel([status]), "limit": 1, "offset": 0},
                api_key=key,
            )
            return res.get("count", 0)

        counts = await asyncio.gather(*(count(s) for s in INCIDENT_STATUSES))
        return dict(zip(INCIDENT_STATUSES, counts))

    @mcp.tool()
    async def list_workflows(ctx: Context = None) -> Any:
        """List workflows configured in Keep."""
        return await keep.get("/workflows", api_key=_request_api_key(ctx))

    @mcp.tool()
    async def get_workflow(workflow_id: str, ctx: Context = None) -> Any:
        """Get a workflow definition by id."""
        return await keep.get(
            f"/workflows/{seg(workflow_id)}", api_key=_request_api_key(ctx)
        )

    @mcp.tool()
    async def list_workflow_runs(
        workflow_id: str,
        status: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        ctx: Context = None,
    ) -> Any:
        """List executions of a workflow, optionally filtered by status."""
        return await keep.get(
            f"/workflows/{seg(workflow_id)}/runs",
            params={"status": status, "limit": _clamp(limit), "offset": max(0, offset)},
            api_key=_request_api_key(ctx),
        )

    @mcp.tool()
    async def get_workflow_run(
        workflow_id: str, execution_id: str, ctx: Context = None
    ) -> Any:
        """Get a workflow execution's status, results and logs."""
        return await keep.get(
            f"/workflows/{seg(workflow_id)}/runs/{seg(execution_id)}",
            api_key=_request_api_key(ctx),
        )

    @mcp.tool()
    async def get_alert_workflow_executions(ctx: Context = None) -> Any:
        """Latest workflow executions per alert fingerprint."""
        return await keep.get("/workflows/executions", api_key=_request_api_key(ctx))

    if settings.enable_writes:
        # Writes are opt-in; Keep RBAC on the caller's key still applies.
        def audit(tool: str, ctx: Context | None, **args: Any) -> None:
            key = _request_api_key(ctx) or settings.keep_api_key or ""
            who = hashlib.sha256(key.encode()).hexdigest()[:8]
            logger.info("AUDIT tool=%s key_id=%s args=%r", tool, who, args)

        @mcp.tool(annotations=WRITE_HINTS)
        async def change_incident_status(
            incident_id: str,
            status: str,
            comment: str | None = None,
            ctx: Context = None,
        ) -> Any:
            """Change an incident's status (firing, acknowledged, resolved)."""
            if status not in CHANGEABLE_INCIDENT_STATUSES:
                raise ValueError(
                    f"status must be one of {list(CHANGEABLE_INCIDENT_STATUSES)}"
                )
            audit("change_incident_status", ctx, incident_id=incident_id, status=status)
            return await keep.post(
                f"/incidents/{seg(incident_id)}/status",
                json={"status": status, "comment": comment},
                api_key=_request_api_key(ctx),
            )

        @mcp.tool(annotations=WRITE_HINTS)
        async def add_alert_note(
            fingerprint: str, note: str, ctx: Context = None
        ) -> Any:
            """Attach a note to an alert."""
            audit("add_alert_note", ctx, fingerprint=fingerprint)
            return await keep.post(
                "/alerts/enrich/note",
                json={"fingerprint": fingerprint, "note": note},
                api_key=_request_api_key(ctx),
            )

        @mcp.tool(annotations=RUN_HINTS)
        async def run_workflow(
            workflow_id: str,
            params: dict[str, Any] | None = None,
            dry_run: bool = True,
            ctx: Context = None,
        ) -> Any:
            """Run a workflow manually. Defaults to dry_run=True, which only
            returns the request that would be sent; pass dry_run=false to execute."""
            planned = {"workflow_id": workflow_id, "body": params or {}}
            if dry_run:
                return {"dry_run": True, "would_run": planned}
            audit("run_workflow", ctx, workflow_id=workflow_id)
            return await keep.post(
                f"/workflows/{seg(workflow_id)}/run",
                json=params or {},
                api_key=_request_api_key(ctx),
            )

    @mcp.prompt()
    def triage_alert(fingerprint: str) -> str:
        """Guide an agent through triaging a single alert."""
        return (
            f"Triage the Keep alert with fingerprint `{fingerprint}`.\n"
            "1. Call get_alert_history to see how it evolved (status, severity, frequency).\n"
            "2. Call search_alerts with a CEL expression on the same service/source to "
            "find related firing alerts.\n"
            '3. Call list_incidents(status=["firing", "acknowledged"]) and, for any '
            "incident that contains this alert, call get_incident_with_alerts.\n"
            "4. Call get_topology filtered by the affected service to identify upstream "
            "and downstream dependencies.\n"
            "Finish with: likely cause, blast radius, and recommended next steps. "
            "Do not claim facts that the tools did not return."
        )

    @mcp.resource("keep://incidents/{incident_id}")
    async def incident_resource(incident_id: str) -> Any:
        """A single incident."""
        return await keep.get(
            f"/incidents/{seg(incident_id)}",
            api_key=_request_api_key(mcp.get_context()),
        )

    @mcp.resource("keep://alerts/{fingerprint}")
    async def alert_resource(fingerprint: str) -> Any:
        """History of a single alert by fingerprint."""
        return await keep.get(
            f"/alerts/{seg(fingerprint)}/history",
            api_key=_request_api_key(mcp.get_context()),
        )

    @mcp.resource("keep://topology")
    async def topology_resource() -> Any:
        """The full service topology."""
        return await keep.get("/topology", api_key=_request_api_key(mcp.get_context()))

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(_: Request) -> JSONResponse:
        try:
            await keep.get("/healthcheck", public=True)
        except KeepAPIError as exc:
            logger.warning("Readiness check failed: %s", exc)
            return JSONResponse({"status": "unavailable"}, 503)
        return JSONResponse({"status": "ready"})

    return mcp


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    create_server(settings).run(transport=settings.transport)


if __name__ == "__main__":
    main()
