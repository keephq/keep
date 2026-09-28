"""
Unit tests for the dephealth topology provider.

vm_topology_response.json / vm_latency_response.json are real instant-query
responses from a VictoriaMetrics instance scraping the uniproxy test
topology: 20 edges, 2 applications (proxy-cluster-1, proxy-cluster-2) with
shared dependency nodes (postgresql, uniproxy-04).
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.dephealth_provider.dephealth_provider import (
    DEFAULT_LATENCY_QUERY,
    DEFAULT_TOPOLOGY_QUERY,
    DephealthProvider,
)
from keep.providers.models.provider_config import ProviderConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VICTORIAMETRICS_URL = "http://victoriametrics.example.com:8428"
PROVIDER_ID = "dephealth-test"


def _build_provider(**authentication) -> DephealthProvider:
    config = ProviderConfig(
        description="Dephealth Provider",
        authentication={"url": VICTORIAMETRICS_URL, **authentication},
    )
    return DephealthProvider(ContextManager(tenant_id="test"), PROVIDER_ID, config)


def _fixture(fixture: str) -> dict:
    with open(FIXTURES_DIR / fixture) as f:
        return json.load(f)


def _mock_vm(
    mock_get,
    topology: str = "vm_topology_response.json",
    latency: str = "vm_latency_response.json",
    latency_status: int = 200,
):
    """Route requests.get to the fixture matching the query text."""

    def _respond(url, params=None, **kwargs):
        response = MagicMock()
        query = (params or {}).get("query", "")
        if "latency" in query:
            response.status_code = latency_status
            response.content = b"boom" if latency_status != 200 else b""
            if latency_status == 200:
                response.json.return_value = _fixture(latency)
        else:
            response.status_code = 200
            response.json.return_value = _fixture(topology)
        return response

    mock_get.side_effect = _respond


def _latency_seconds(service: str, dependency: str) -> float:
    for series in _fixture("vm_latency_response.json")["data"]["result"]:
        if (
            series["metric"].get("name") == service
            and series["metric"].get("dependency") == dependency
        ):
            return float(series["value"][1])
    raise AssertionError(f"no latency series for {service} -> {dependency}")


class TestValidateConfig:
    def test_defaults(self):
        provider = _build_provider()
        assert str(provider.authentication_config.url).rstrip("/") == (
            VICTORIAMETRICS_URL
        )
        assert provider.authentication_config.query == DEFAULT_TOPOLOGY_QUERY
        assert provider.authentication_config.latency_query == (DEFAULT_LATENCY_QUERY)
        assert provider.authentication_config.verify is True
        assert provider.authentication_config.service_label == "name"
        assert provider.authentication_config.namespace_label == "namespace"
        assert provider.authentication_config.group_label == "group"
        assert provider.authentication_config.dependency_label == "dependency"
        assert provider.authentication_config.protocol_label == "type"
        assert provider.authentication_config.critical_label == "critical"
        assert provider.authentication_config.entry_label == "isentry"

    def test_custom_configuration(self):
        provider = _build_provider(
            query="group by (svc, dep, kind) (custom_metric)",
            service_label="svc",
            dependency_label="dep",
            protocol_label="kind",
            latency_query="",
            verify=False,
        )
        assert provider.authentication_config.query == (
            "group by (svc, dep, kind) (custom_metric)"
        )
        assert provider.authentication_config.service_label == "svc"
        assert provider.authentication_config.dependency_label == "dep"
        assert provider.authentication_config.protocol_label == "kind"
        assert provider.authentication_config.latency_query == ""
        assert provider.authentication_config.verify is False


class TestPullTopology:
    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_builds_topology_from_real_metrics(self, mock_get):
        _mock_vm(mock_get)
        services, extra = _build_provider().pull_topology()
        assert extra == {}
        by_name = {service.service: service for service in services}

        assert len(services) == 17
        assert sum(len(s.dependencies) for s in services) == 20

        # reporters carry namespace, group tag and provider ownership
        reporter = by_name["uniproxy-01"]
        assert reporter.namespace == "dephealth-uniproxy"
        assert reporter.display_name == "uniproxy-01"
        assert "proxy-cluster-1" in reporter.tags
        assert "entry" in reporter.tags  # isentry=yes
        assert reporter.source_provider_id == PROVIDER_ID

        # dependency-only nodes exist as services without metrics of their own
        postgres = by_name["postgresql"]
        assert postgres.namespace is None
        assert "critical" in postgres.tags  # critical=yes edge from uniproxy-03
        assert postgres.dependencies == {}

        # edge protocols carry type and average check latency
        expected_ms = _latency_seconds("uniproxy-03", "postgresql") * 1000
        assert by_name["uniproxy-03"].dependencies["postgresql"] == (
            f"postgres · {expected_ms:.1f}ms"
        )

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_applications_are_stable_and_shared(self, mock_get):
        _mock_vm(mock_get)
        services, _ = _build_provider().pull_topology()
        by_name = {service.service: service for service in services}

        app1_id = uuid.uuid5(uuid.NAMESPACE_DNS, "proxy-cluster-1")
        app2_id = uuid.uuid5(uuid.NAMESPACE_DNS, "proxy-cluster-2")
        # shared nodes belong to both applications
        for shared in ("postgresql", "uniproxy-04"):
            assert by_name[shared].application_relations == {
                app1_id: "proxy-cluster-1",
                app2_id: "proxy-cluster-2",
            }
        assert by_name["uniproxy-01"].application_relations == {
            app1_id: "proxy-cluster-1"
        }

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_custom_label_mapping(self, mock_get):
        _mock_vm(mock_get, topology="vm_renamed_labels_response.json")
        provider = _build_provider(
            query="group by (svc, dep, kind) (custom_metric)",
            service_label="svc",
            dependency_label="dep",
            protocol_label="kind",
        )
        services, _ = provider.pull_topology()
        by_name = {service.service: service for service in services}
        assert len(services) == 4
        # latency fixture uses the default labels, so nothing matches and
        # protocols stay bare
        assert by_name["billing-api"].dependencies["postgres-main"] == "postgres"
        assert by_name["order-api"].dependencies["payment-api"] == "http"

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_latency_disabled_keeps_bare_protocols(self, mock_get):
        _mock_vm(mock_get)
        services, _ = _build_provider(latency_query="").pull_topology()
        by_name = {service.service: service for service in services}
        assert by_name["uniproxy-03"].dependencies["postgresql"] == "postgres"
        assert mock_get.call_count == 1

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_latency_failure_is_best_effort(self, mock_get):
        _mock_vm(mock_get, latency_status=500)
        services, _ = _build_provider().pull_topology()
        by_name = {service.service: service for service in services}
        # topology is still pulled, protocols stay without latency
        assert len(services) == 17
        assert by_name["uniproxy-03"].dependencies["postgresql"] == "postgres"

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_query_error_raises(self, mock_get):
        response = MagicMock()
        response.status_code = 500
        response.content = b"boom"
        mock_get.return_value = response
        provider = _build_provider()
        with pytest.raises(Exception, match="dephealth query failed"):
            provider.pull_topology()

    def test_format_latency(self):
        assert DephealthProvider._format_latency(0.011368) == "11.4ms"
        assert DephealthProvider._format_latency(0.5) == "500.0ms"
        assert DephealthProvider._format_latency(999.999e-3) == "1000.0ms"
        assert DephealthProvider._format_latency(1.5) == "1.50s"


class TestValidateScopes:
    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_connectivity_ok(self, mock_get):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "success", "data": {"result": []}}
        mock_get.return_value = response
        scopes = _build_provider().validate_scopes()
        assert scopes == {"connectivity": True}
        # the connectivity probe runs a lightweight `up` query
        assert mock_get.call_args.kwargs["params"] == {"query": "up"}

    @patch("keep.providers.dephealth_provider.dephealth_provider.requests.get")
    def test_connectivity_failure_reports_error(self, mock_get):
        response = MagicMock()
        response.status_code = 401
        response.content = b"unauthorized"
        mock_get.return_value = response
        scopes = _build_provider().validate_scopes()
        assert isinstance(scopes["connectivity"], str)
        assert "dephealth query failed" in scopes["connectivity"]
