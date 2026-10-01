"""Auth0 verifier construction must not reach the network.

OIDC discovery happens once, when the module is imported. Building a verifier
reuses that answer, and route dependencies build a lot of verifiers.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

MODULE = "ee.identitymanager.identity_managers.auth0.auth0_authverifier"
DOMAIN = "example.auth0.com"


@pytest.fixture
def auth0_module(monkeypatch):
    """Import the verifier module fresh, with discovery answered by a stub.

    The module reads AUTH0_DOMAIN and runs discovery at import time, so a stale
    copy in sys.modules would answer for whatever the previous test set.
    """
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", "keep-api")
    sys.modules.pop(MODULE, None)

    response = MagicMock()
    response.json.return_value = {
        "jwks_uri": f"https://{DOMAIN}/.well-known/jwks.json"
    }
    response.raise_for_status = MagicMock()

    requested = []

    def fake_get(url, **kwargs):
        requested.append(url)
        return response

    with patch("requests.get", side_effect=fake_get):
        module = importlib.import_module(MODULE)
        yield module, requested

    sys.modules.pop(MODULE, None)


def test_import_discovers_the_jwks_uri_once(auth0_module):
    module, requested = auth0_module

    assert requested == [f"https://{DOMAIN}/.well-known/openid-configuration"]
    assert module.jwks_uri == f"https://{DOMAIN}/.well-known/jwks.json"


def test_construction_does_not_repeat_discovery(auth0_module):
    module, requested = auth0_module
    requested.clear()

    for _ in range(3):
        module.Auth0AuthVerifier()

    assert requested == []


def test_construction_carries_the_discovered_jwks_uri(auth0_module):
    module, _ = auth0_module

    verifier = module.Auth0AuthVerifier()

    assert verifier.jwks_uri == f"https://{DOMAIN}/.well-known/jwks.json"
