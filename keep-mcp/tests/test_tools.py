import httpx
import pytest
import respx

from keep_mcp import __main__ as mcp

BASE = "http://keep-backend:8080"


@pytest.mark.parametrize(
    "call, method, path",
    [
        (lambda: mcp.search_alerts(cel='severity == "critical"'), "POST", "/alerts/query"),
        (lambda: mcp.list_incidents(), "GET", "/incidents"),
        (lambda: mcp.get_incident("inc-1"), "GET", "/incidents/inc-1"),
        (lambda: mcp.list_incident_alerts("inc-1"), "GET", "/incidents/inc-1/alerts"),
        (lambda: mcp.get_topology(), "GET", "/topology"),
    ],
)
@respx.mock
async def test_tool_calls_expected_endpoint_with_api_key(call, method, path):
    route = respx.request(method, BASE + path).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    assert await call() == {"ok": True}
    assert route.calls.last.request.headers["X-API-KEY"] == mcp.API_KEY


@respx.mock
async def test_list_incidents_repeats_multivalued_params():
    route = respx.get(BASE + "/incidents").mock(return_value=httpx.Response(200, json={}))
    await mcp.list_incidents(status=["firing", "acknowledged"], severity=["critical"])
    url = route.calls.last.request.url
    assert url.params.get_list("status") == ["firing", "acknowledged"]
    assert url.params.get_list("severity") == ["critical"]


@pytest.mark.parametrize(
    "given, expected",
    [(25, 25), (0, 1), (-5, 1), (1000, mcp.MAX_LIMIT)],
)
@respx.mock
async def test_limit_is_clamped(given, expected):
    route = respx.post(BASE + "/alerts/query").mock(return_value=httpx.Response(200, json={}))
    await mcp.search_alerts(limit=given)
    assert route.calls.last.request.read().decode().count(f'"limit": {expected}') == 1


@respx.mock
async def test_non_2xx_raises():
    respx.post(BASE + "/alerts/query").mock(
        return_value=httpx.Response(400, json={"detail": "bad cel"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await mcp.search_alerts(cel="!!!")


def test_missing_api_key_exits(monkeypatch):
    monkeypatch.setattr(mcp, "API_KEY", "")
    with pytest.raises(SystemExit) as exc:
        mcp.main()
    assert exc.value.code == 2
