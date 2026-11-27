import json
from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.appdynamics_provider.appdynamics_provider import AppdynamicsProvider
from keep.providers.models.provider_config import ProviderConfig


def _build_provider() -> AppdynamicsProvider:
    config = ProviderConfig(
        description="AppDynamics Provider",
        authentication={
            "appDynamicsAccountName": "test-account",
            "appId": "12345",
            "host": "https://test.saas.appdynamics.com",
            "appDynamicsUsername": "test-user",
            "appDynamicsPassword": "test-password",
        },
    )
    return AppdynamicsProvider(
        ContextManager(tenant_id="test"), "appdynamics-test", config
    )


@pytest.mark.parametrize(
    "url, expected_scheme, expected_host, expected_path, expected_query",
    [
        (
            "https://soc.example.com/alerts/event?provider_id=123",
            "HTTPS",
            "soc.example.com/alerts",
            "/event",
            "provider_id=123",
        ),
        (
            "http://host.docker.internal:8080/alerts/event?provider_id=123",
            "HTTP",
            "host.docker.internal:8080/alerts",
            "/event",
            "provider_id=123",
        ),
        (
            "https://tenant1.example.com/alerts/event?provider_id=123",
            "HTTPS",
            "tenant1.example.com/alerts",
            "/event",
            "provider_id=123",
        ),
        (
            "https://hq-keep.example.com/alerts/event?provider_id=123",
            "HTTPS",
            "hq-keep.example.com/alerts",
            "/event",
            "provider_id=123",
        ),
        (
            "https://api.keephq.dev/alerts/event?provider_id=123",
            "HTTPS",
            "api.keephq.dev/alerts",
            "/event",
            "provider_id=123",
        ),
        (
            "http://localhost:8080/alerts/event",
            "HTTP",
            "localhost:8080/alerts",
            "/event",
            "",
        ),
    ],
)
def test_create_http_response_template_host_scheme_parsing(
    url, expected_scheme, expected_host, expected_path, expected_query
):
    provider = _build_provider()
    captured_template = {}

    def mock_post(url, files=None, headers=None, auth=None):
        nonlocal captured_template
        files["template"].seek(0)
        captured_template = json.load(files["template"])
        res = MagicMock()
        res.json.return_value = {"success": True}
        return res

    with patch("requests.post", side_effect=mock_post):
        provider._AppdynamicsProvider__create_http_response_template(
            keep_api_url=url, api_key="secret-api-key"
        )

    assert len(captured_template) > 0
    tpl = captured_template[0]
    assert tpl["scheme"] == expected_scheme
    assert tpl["host"] == expected_host
    assert tpl["path"] == expected_path
    assert tpl["query"] == expected_query
    assert tpl["headers"][0]["value"] == "secret-api-key"
