"""Tests for exposing a PromQL query as a provider method (issue #6475).

The provider could already run instant queries through _query(), but
PROVIDER_METHODS was empty, so the UI and agents reported `methods: []` and had
no way to reach it. These tests cover the new query_instant() method and the
invariants ProvidersFactory relies on when it reflects PROVIDER_METHODS.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.prometheus_provider.prometheus_provider import PrometheusProvider

RESULT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"__name__": "up", "job": "prometheus"}, "value": [1, "1"]}
        ],
    },
}


def _build_provider(**auth) -> PrometheusProvider:
    config = ProviderConfig(
        description="Prometheus Provider",
        authentication={"url": "http://prometheus.example.com", **auth},
    )
    return PrometheusProvider(ContextManager(tenant_id="test"), "prom-test", config)


def _response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.content = b"error"
    response.json = MagicMock(return_value=payload)
    return response


class TestProviderMethodIsDiscoverable:
    """ProvidersFactory reflects PROVIDER_METHODS; these are its preconditions."""

    def test_provider_exposes_a_method(self):
        assert PrometheusProvider.PROVIDER_METHODS, "provider still reports no methods"

    def test_func_name_resolves_on_the_class_itself(self):
        """__get_methods uses provider_class.__dict__, so an inherited method
        would make inspect.signature(None) raise at provider-load time."""
        for method in PrometheusProvider.PROVIDER_METHODS:
            assert PrometheusProvider.__dict__.get(method.func_name) is not None

    def test_declared_scopes_exist_on_the_provider(self):
        declared = {scope.name for scope in PrometheusProvider.PROVIDER_SCOPES}
        for method in PrometheusProvider.PROVIDER_METHODS:
            assert set(method.scopes) <= declared

    def test_query_is_a_read_only_view(self):
        method = PrometheusProvider.PROVIDER_METHODS[0]
        assert method.type == "view"


class TestQueryInstant:
    def test_hits_the_instant_query_endpoint(self):
        provider = _build_provider()
        with patch("requests.get", return_value=_response(RESULT)) as get:
            provider.query_instant('up{job="prometheus"}')
        args, kwargs = get.call_args
        assert args[0] == "http://prometheus.example.com/api/v1/query"
        assert kwargs["params"] == {"query": 'up{job="prometheus"}'}

    def test_returns_the_response_envelope(self):
        provider = _build_provider()
        with patch("requests.get", return_value=_response(RESULT)):
            assert provider.query_instant("up") == RESULT

    def test_empty_query_is_rejected(self):
        provider = _build_provider()
        with pytest.raises(ValueError):
            provider.query_instant("")

    def test_non_200_raises(self):
        provider = _build_provider()
        with patch("requests.get", return_value=_response({}, status_code=500)):
            with pytest.raises(Exception, match="Prometheus query failed"):
                provider.query_instant("up")

    def test_basic_auth_used_when_credentials_are_set(self):
        provider = _build_provider(username="u", password="p")
        with patch("requests.get", return_value=_response(RESULT)) as get:
            provider.query_instant("up")
        auth = get.call_args.kwargs["auth"]
        assert auth is not None
        assert (auth.username, auth.password) == ("u", "p")

    def test_no_auth_when_credentials_are_absent(self):
        provider = _build_provider()
        with patch("requests.get", return_value=_response(RESULT)) as get:
            provider.query_instant("up")
        assert get.call_args.kwargs["auth"] is None
