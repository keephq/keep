"""Tests for querying Grafana datasources through /api/ds/query."""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.grafana_provider.grafana_provider import GrafanaProvider
from keep.providers.models.provider_config import ProviderConfig

PROM_FRAME = {
    "schema": {"fields": [{"name": "Time"}, {"name": "Value"}]},
    "data": {"values": [[1785959838794], [1611]]},
}
SQL_FRAME = {
    "schema": {"fields": [{"name": "provider_id"}, {"name": "c"}]},
    "data": {"values": [["a", "b"], [3884296, 1849312]]},
}


def _build_provider() -> GrafanaProvider:
    config = ProviderConfig(
        description="Grafana Provider",
        authentication={"host": "https://grafana.example.com", "token": "t"},
    )
    return GrafanaProvider(ContextManager(tenant_id="test"), "grafana-test", config)


def _response(payload, ok=True, status_code=200):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.text = "error body"
    response.json = MagicMock(return_value=payload)
    return response


class TestFramesToRows:
    def test_sql_frame_becomes_rows(self):
        assert GrafanaProvider._frames_to_rows([SQL_FRAME]) == [
            {"provider_id": "a", "c": 3884296},
            {"provider_id": "b", "c": 1849312},
        ]

    def test_multiple_frames_are_concatenated(self):
        rows = GrafanaProvider._frames_to_rows([PROM_FRAME, SQL_FRAME])
        assert len(rows) == 3
        assert rows[0] == {"Time": 1785959838794, "Value": 1611}

    @pytest.mark.parametrize("frames", [[], [{}], [{"schema": {"fields": []}}]])
    def test_empty_input_is_not_an_error(self, frames):
        assert GrafanaProvider._frames_to_rows(frames) == []


def test_query_builds_payload_and_returns_rows():
    provider = _build_provider()
    payload = {"results": {"A": {"frames": [SQL_FRAME]}}}
    with patch("requests.post", return_value=_response(payload)) as post:
        rows = provider._query(
            datasource_uid="ds-uid", raw_sql="SELECT 1", start="now-6h", end="now"
        )

    assert rows[0]["provider_id"] == "a"
    sent = post.call_args.kwargs["json"]
    assert sent["from"] == "now-6h"
    assert sent["queries"][0]["datasource"] == {"uid": "ds-uid"}
    assert sent["queries"][0]["rawSql"] == "SELECT 1"


def test_explicit_query_dict_overrides_defaults():
    provider = _build_provider()
    with patch(
        "requests.post", return_value=_response({"results": {"A": {"frames": []}}})
    ) as post:
        provider._query(
            datasource_uid="ds-uid",
            expr="up",
            query={"expr": "count(up)", "hide": True},
        )

    target = post.call_args.kwargs["json"]["queries"][0]
    assert target["expr"] == "count(up)"
    assert target["hide"] is True


def test_missing_datasource_uid_raises():
    provider = _build_provider()
    with pytest.raises(ProviderException, match="datasource_uid is required"):
        provider._query(expr="up")


def test_http_error_raises():
    provider = _build_provider()
    with patch("requests.post", return_value=_response({}, ok=False, status_code=403)):
        with pytest.raises(ProviderException, match="403"):
            provider._query(datasource_uid="ds-uid", expr="up")


def test_datasource_error_raises():
    provider = _build_provider()
    payload = {"results": {"A": {"error": "table not found"}}}
    with patch("requests.post", return_value=_response(payload)):
        with pytest.raises(ProviderException, match="table not found"):
            provider._query(datasource_uid="ds-uid", raw_sql="SELECT 1")
