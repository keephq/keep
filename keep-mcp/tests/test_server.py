import json

import httpx
import pytest
from keep_mcp.client import KeepClient
from keep_mcp.config import Settings
from keep_mcp.server import create_server


@pytest.fixture
def calls():
    return []


@pytest.fixture
def server(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/healthcheck":
            return httpx.Response(200, json={"status": "OK"})
        if path == "/boom":
            return httpx.Response(500, text="nope")
        if path in ("/incidents", "/alerts/query"):
            return httpx.Response(200, json={"count": 2, "items": []})
        if path.endswith("/alerts"):
            return httpx.Response(200, json={"items": [{"id": "a1"}], "count": 1})
        if path.startswith("/incidents/"):
            return httpx.Response(200, json={"id": path.split("/")[2]})
        return httpx.Response(200, json=[{"path": path}])

    client = KeepClient("http://keep", "secret", transport=httpx.MockTransport(handler))
    return create_server(Settings(), client)


async def call(server, name, args):
    result = await server.call_tool(name, args)
    content = result[1] if isinstance(result, tuple) else result
    return content


async def test_tools_registered(server):
    names = {t.name for t in await server.list_tools()}
    assert names == {
        "search_alerts",
        "list_incidents",
        "get_incident_with_alerts",
        "get_topology",
        "get_alert_history",
        "get_alert_status_summary",
        "get_incident_status_summary",
        "list_workflows",
        "get_workflow",
        "list_workflow_runs",
        "get_workflow_run",
        "get_alert_workflow_executions",
    }


async def test_resources_registered(server):
    templates = {str(t.uriTemplate) for t in await server.list_resource_templates()}
    resources = {str(r.uri) for r in await server.list_resources()}
    assert templates == {
        "keep://incidents/{incident_id}",
        "keep://alerts/{fingerprint}",
    }
    assert resources == {"keep://topology"}


async def test_search_alerts_posts_query_with_api_key(server, calls):
    await call(server, "search_alerts", {"cel": 'severity == "critical"', "limit": 10})
    req = calls[-1]
    assert req.method == "POST" and req.url.path == "/alerts/query"
    assert req.headers["x-api-key"] == "secret"
    body = json.loads(req.content)
    assert body["cel"] == 'severity == "critical"' and body["limit"] == 10


async def test_search_alerts_clamps_limit(server, calls):
    await call(server, "search_alerts", {"limit": 100000})
    assert json.loads(calls[-1].content)["limit"] == 200


async def test_list_incidents_repeats_status_param(server, calls):
    await call(server, "list_incidents", {"status": ["firing", "acknowledged"]})
    assert (
        calls[-1].url.params["cel"] == 'status == "firing" || status == "acknowledged"'
    )
    assert "status" not in calls[-1].url.params


async def test_list_incidents_rejects_bad_status(server):
    with pytest.raises(Exception, match="Invalid status"):
        await call(server, "list_incidents", {"status": ["bogus"]})


async def test_get_incident_with_alerts(server, calls):
    await call(
        server, "get_incident_with_alerts", {"incident_id": "abc", "alerts_offset": 50}
    )
    assert calls[-1].url.params["offset"] == "50"
    calls.clear()
    await call(server, "get_incident_with_alerts", {"incident_id": "abc"})
    assert [c.url.path for c in calls] == ["/incidents/abc", "/incidents/abc/alerts"]


async def test_get_topology_omits_unset_filters(server, calls):
    await call(server, "get_topology", {"environment": "prod"})
    assert dict(calls[-1].url.params) == {"environment": "prod"}


async def test_backend_error_surfaces(server):
    client = KeepClient(
        "http://keep",
        transport=httpx.MockTransport(lambda r: httpx.Response(500, text="nope")),
    )
    from keep_mcp.client import KeepAPIError

    with pytest.raises(KeepAPIError, match="500"):
        await client.get("/boom")


async def test_http_mode_has_no_env_key_fallback(calls):
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    s = Settings(transport="streamable-http", keep_api_key="envkey")
    srv = create_server(s)  # default client; patch below
    from keep_mcp import server as _  # noqa: F401

    client = KeepClient("http://keep", None, transport=httpx.MockTransport(handler))
    srv = create_server(s, client)
    await srv.call_tool("get_topology", {})
    assert "x-api-key" not in calls[-1].headers


async def test_resource_requests_use_default_key_in_stdio(server, calls):
    await server.read_resource("keep://topology")
    assert calls[-1].headers["x-api-key"] == "secret"


async def test_alert_history_tool(server, calls):
    await call(server, "get_alert_history", {"fingerprint": "fp1"})
    assert calls[-1].url.path == "/alerts/fp1/history"


async def test_triage_prompt(server):
    prompts = {p.name for p in await server.list_prompts()}
    assert prompts == {"triage_alert"}
    res = await server.get_prompt("triage_alert", {"fingerprint": "fp1"})
    assert "fp1" in res.messages[0].content.text


def _write_server(calls, enable=True):
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"count": 3})

    client = KeepClient("http://keep", "secret", transport=httpx.MockTransport(handler))
    return create_server(Settings(enable_writes=enable), client)


async def test_status_summaries(server, calls):
    await call(server, "get_incident_status_summary", {})
    assert len(calls) == 5
    assert all(c.url.params["limit"] == "1" for c in calls)
    assert {c.url.params["cel"] for c in calls} == {
        f'status == "{s}"'
        for s in ("firing", "resolved", "acknowledged", "merged", "deleted")
    }
    await call(server, "get_alert_status_summary", {})
    assert sum(1 for c in calls if c.url.path == "/alerts/query") == 6


async def test_workflow_read_tools(server, calls):
    await call(
        server, "list_workflow_runs", {"workflow_id": "w", "status": ["success"]}
    )
    assert calls[-1].url.path == "/workflows/w/runs"
    await call(server, "get_workflow_run", {"workflow_id": "w", "execution_id": "e"})
    assert calls[-1].url.path == "/workflows/w/runs/e"


async def test_writes_disabled_by_default(server):
    names = {t.name for t in await server.list_tools()}
    assert not names & {"change_incident_status", "add_alert_note", "run_workflow"}


async def test_write_tools_enabled(calls):
    srv = _write_server(calls)
    names = {t.name for t in await srv.list_tools()}
    assert {"change_incident_status", "add_alert_note", "run_workflow"} <= names
    await call(
        srv, "change_incident_status", {"incident_id": "i", "status": "resolved"}
    )
    assert calls[-1].url.path == "/incidents/i/status"
    assert json.loads(calls[-1].content)["status"] == "resolved"
    with pytest.raises(Exception, match="status must be"):
        await call(
            srv, "change_incident_status", {"incident_id": "i", "status": "merged"}
        )


async def test_run_workflow_dry_run_default(calls):
    srv = _write_server(calls)
    await call(srv, "run_workflow", {"workflow_id": "w"})
    assert calls == []
    await call(srv, "run_workflow", {"workflow_id": "w", "dry_run": False})
    assert calls[-1].url.path == "/workflows/w/run"


async def test_path_ids_are_encoded(server, calls):
    await call(server, "get_workflow", {"workflow_id": "../../alerts#x?y=1"})
    assert calls[-1].url.raw_path.startswith(b"/workflows/..%2F..%2Falerts%23x%3Fy%3D1")


async def test_dot_ids_rejected(server):
    with pytest.raises(Exception, match="Invalid identifier"):
        await call(server, "get_incident_with_alerts", {"incident_id": ".."})


async def test_http_mode_requires_key():
    from keep_mcp.client import KeepAPIError

    client = KeepClient(
        "http://keep",
        None,
        require_key=True,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    with pytest.raises(KeepAPIError, match="X-API-KEY"):
        await client.get("/topology")
    assert await client.get("/healthcheck", public=True) == {}


async def test_redirect_is_an_error():
    from keep_mcp.client import KeepAPIError

    client = KeepClient(
        "http://keep",
        "k",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(307, headers={"location": "http://evil/"})
        ),
    )
    with pytest.raises(KeepAPIError, match="307"):
        await client.post("/workflows/w/run")
