import httpx
import pytest
import respx

from keep_mcp import __main__ as mcp


@respx.mock
async def test_search_alerts_posts_cel_with_api_key():
    respx.post("http://keep-backend:8080/alerts/query").mock(
        return_value=httpx.Response(200, json={"results": [{"id": "a"}]})
    )
    data = await mcp.search_alerts(cel='severity == "critical"', limit=5)
    assert data["results"] == [{"id": "a"}]


@respx.mock
async def test_list_incidents_repeats_multivalued_params():
    route = respx.get("http://keep-backend:8080/incidents").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    await mcp.list_incidents(status=["firing", "acknowledged"], severity=["critical"])
    url = route.calls.last.request.url
    assert url.params.get_list("status") == ["firing", "acknowledged"]
    assert url.params.get_list("severity") == ["critical"]


@respx.mock
async def test_non_2xx_raises():
    respx.post("http://keep-backend:8080/alerts/query").mock(
        return_value=httpx.Response(400, json={"detail": "bad cel"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await mcp.search_alerts(cel="!!!")
