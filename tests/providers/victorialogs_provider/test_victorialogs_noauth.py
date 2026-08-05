"""
Tests for the VictoriaLogs provider authentication headers.

generate_auth_headers() had no return statement on the NoAuth path, so it
returned None and every _query() call failed with
"AttributeError: 'NoneType' object has no attribute 'update'".
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.victorialogs_provider.victorialogs_provider import (
    VictorialogsProvider,
)

HOST_URL = "http://victorialogs.example.com:9428"


def _build_provider(**authentication) -> VictorialogsProvider:
    config = ProviderConfig(
        description="VictoriaLogs Provider",
        authentication={"host_url": HOST_URL, **authentication},
    )
    return VictorialogsProvider(
        ContextManager(tenant_id="test"), "victorialogs-test", config
    )


class TestGenerateAuthHeaders:
    def test_noauth_returns_empty_dict(self):
        """NoAuth has no headers to send, but must still return a mapping."""
        provider = _build_provider(authentication_type="NoAuth")
        assert provider.generate_auth_headers() == {}

    def test_noauth_is_the_default(self):
        """authentication_type defaults to NoAuth, so the default must work too."""
        provider = _build_provider()
        assert provider.generate_auth_headers() == {}

    def test_basic_returns_authorization_header(self):
        provider = _build_provider(
            authentication_type="Basic", username="user", password="pass"
        )
        # base64("user:pass")
        assert provider.generate_auth_headers() == {
            "Authorization": "Basic dXNlcjpwYXNz"
        }

    def test_bearer_returns_authorization_header(self):
        provider = _build_provider(
            authentication_type="Bearer", bearer_token="token", x_scope_orgid="org"
        )
        assert provider.generate_auth_headers() == {
            "Authorization": "Bearer token",
            "X-Scope-OrgID": "org",
        }


@pytest.mark.parametrize(
    "query_type,query",
    [
        ("query", "*"),
        ("hits", "*"),
        ("stats_query", "* | stats count()"),
    ],
)
def test_query_with_noauth_does_not_raise(query_type, query):
    """Every query type builds its headers the same way, so all of them broke."""
    provider = _build_provider(authentication_type="NoAuth")

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.text = '{"_msg": "log line"}'
    response.json = MagicMock(return_value={"status": "success"})

    with patch("requests.post", return_value=response) as post:
        provider._query(queryType=query_type, query=query)

    sent_headers = post.call_args.kwargs["headers"]
    assert "Authorization" not in sent_headers
