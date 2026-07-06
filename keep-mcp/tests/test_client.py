from __future__ import annotations

import httpx
import pytest
import respx

from keep_mcp.client import KeepClient


@pytest.fixture
def client() -> KeepClient:
    return KeepClient("http://keep-backend:8080", api_key="test-key", timeout=5.0)


@respx.mock
async def test_query_alerts_sends_cel_and_api_key(client: KeepClient) -> None:
    route = respx.post("http://keep-backend:8080/alerts/query").mock(
        return_value=httpx.Response(
            200, json={"limit": 5, "offset": 0, "count": 1, "results": [{"id": "a"}]}
        )
    )

    data = await client.query_alerts(cel='severity == "critical"', limit=5)

    assert route.called
    assert route.calls.last.request.headers["X-API-KEY"] == "test-key"
    assert data["results"] == [{"id": "a"}]


@respx.mock
async def test_list_incidents_repeats_status_and_severity(client: KeepClient) -> None:
    route = respx.get("http://keep-backend:8080/incidents").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    await client.list_incidents(
        status=["firing", "acknowledged"], severity=["critical"], limit=10
    )

    url = route.calls.last.request.url
    assert url.params.get_list("status") == ["firing", "acknowledged"]
    assert url.params.get_list("severity") == ["critical"]
    assert url.params["limit"] == "10"


@respx.mock
async def test_get_incident_and_alerts(client: KeepClient) -> None:
    incident_id = "11111111-1111-1111-1111-111111111111"
    respx.get(f"http://keep-backend:8080/incidents/{incident_id}").mock(
        return_value=httpx.Response(200, json={"id": incident_id, "status": "firing"})
    )
    respx.get(f"http://keep-backend:8080/incidents/{incident_id}/alerts").mock(
        return_value=httpx.Response(200, json={"count": 0, "items": []})
    )

    incident = await client.get_incident(incident_id)
    alerts = await client.get_incident_alerts(incident_id, limit=5)

    assert incident["id"] == incident_id
    assert alerts["items"] == []


@respx.mock
async def test_non_2xx_raises_httpx_error(client: KeepClient) -> None:
    respx.post("http://keep-backend:8080/alerts/query").mock(
        return_value=httpx.Response(400, json={"detail": "bad cel"})
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.query_alerts(cel="!!!")

    assert exc_info.value.response.status_code == 400


def test_missing_api_key_raises() -> None:
    with pytest.raises(ValueError):
        KeepClient("http://x", api_key="")
