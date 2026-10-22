"""Tests for Auth0AuthVerifier: no redundant OIDC discovery on construction.

Issue #6781 — every call to Auth0AuthVerifier.__init__ was firing an extra
requests.get() to the OpenID discovery endpoint and throwing the result away.

These tests verify:
1. The module-level _discover_jwks_uri is called exactly once (at import).
2. Constructing Auth0AuthVerifier N times does NOT call _discover_jwks_uri
   again (only the module-level call is expected).
3. self.jwks_uri is set to the module-level jwks_uri (not re-discovered).
"""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers to import the module under test with a stubbed environment and HTTP
# ---------------------------------------------------------------------------

DISCOVERY_URL_RESPONSE = {"jwks_uri": "https://example.auth0.com/.well-known/jwks.json"}
EXPECTED_JWKS_URI = "https://example.auth0.com/.well-known/jwks.json"


def _make_requests_stub(side_effect=None):
    """Return a mock requests module whose get() returns the discovery JSON."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = DISCOVERY_URL_RESPONSE

    stub = MagicMock()
    if side_effect is not None:
        stub.get.side_effect = side_effect
    else:
        stub.get.return_value = mock_resp
    return stub


def _import_authverifier_fresh(env, requests_stub):
    """
    Import auth0_authverifier in isolation with a controlled environment and
    a stubbed requests module.  Returns the module object.
    """
    module_name = "ee.identitymanager.identity_managers.auth0.auth0_authverifier"
    # Remove any cached copy so the module-level code runs fresh.
    for key in list(sys.modules.keys()):
        if "auth0_authverifier" in key or "auth0_identitymanager" in key:
            del sys.modules[key]

    with patch.dict(os.environ, env, clear=False), patch.dict(
        sys.modules,
        {
            "requests": requests_stub,
            "jwt": _make_jwt_stub(),
            "fastapi": _make_fastapi_stub(),
            "keep.identitymanager.authenticatedentity": _make_module_stub(
                "AuthenticatedEntity"
            ),
            "keep.identitymanager.authverifierbase": _make_authverifierbase_stub(),
            "keep.identitymanager.rbac": _make_module_stub("Admin"),
            "opentelemetry": _make_opentelemetry_stub(),
            "opentelemetry.trace": _make_opentelemetry_stub().trace,
        },
    ):
        mod = importlib.import_module(module_name)
    return mod


# ---------------------------------------------------------------------------
# Stub factories
# ---------------------------------------------------------------------------


def _make_jwt_stub():
    stub = MagicMock()
    stub.PyJWKClient.return_value = MagicMock()
    return stub


def _make_fastapi_stub():
    stub = MagicMock()
    stub.HTTPException = Exception
    return stub


def _make_module_stub(*attr_names):
    m = types.ModuleType("stub")
    for name in attr_names:
        cls = MagicMock()
        cls.get_name.return_value = name
        setattr(m, name, cls)
    return m


def _make_authverifierbase_stub():
    m = types.ModuleType("authverifierbase_stub")

    class AuthVerifierBase:
        def __init__(self, scopes):
            self.scopes = scopes
            self.logger = MagicMock()

    m.AuthVerifierBase = AuthVerifierBase
    return m


def _make_opentelemetry_stub():
    stub = MagicMock()
    stub.trace = MagicMock()
    stub.trace.get_tracer.return_value = MagicMock()
    return stub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuth0AuthVerifierNoRedundantDiscovery(unittest.TestCase):

    def test_discovery_called_once_at_module_import(self):
        """_discover_jwks_uri is called exactly once — at module import."""
        requests_stub = _make_requests_stub()
        env = {"AUTH0_DOMAIN": "example.auth0.com"}
        _import_authverifier_fresh(env, requests_stub)
        assert requests_stub.get.call_count == 1

    def test_three_constructions_do_not_call_discovery_again(self):
        """Constructing Auth0AuthVerifier 3 times must not add extra discoveries."""
        requests_stub = _make_requests_stub()
        env = {"AUTH0_DOMAIN": "example.auth0.com"}
        mod = _import_authverifier_fresh(env, requests_stub)

        before = requests_stub.get.call_count  # 1 from module-level import
        with patch.dict(os.environ, env):
            mod.Auth0AuthVerifier()
            mod.Auth0AuthVerifier()
            mod.Auth0AuthVerifier()

        after = requests_stub.get.call_count
        assert after == before, (
            f"Expected no extra discovery calls after construction, "
            f"but got {after - before} additional call(s)"
        )

    def test_jwks_uri_attribute_set_from_module_level(self):
        """self.jwks_uri must equal the module-level jwks_uri (no re-discovery)."""
        requests_stub = _make_requests_stub()
        env = {"AUTH0_DOMAIN": "example.auth0.com"}
        mod = _import_authverifier_fresh(env, requests_stub)

        with patch.dict(os.environ, env):
            verifier = mod.Auth0AuthVerifier()

        assert verifier.jwks_uri == EXPECTED_JWKS_URI

    def test_missing_auth0_domain_raises(self):
        """Construction without AUTH0_DOMAIN must raise immediately."""
        requests_stub = _make_requests_stub()
        env = {}
        # Remove AUTH0_DOMAIN from environment for this test
        clean_env = {k: v for k, v in os.environ.items() if k != "AUTH0_DOMAIN"}
        mod = _import_authverifier_fresh({"AUTH0_DOMAIN": "example.auth0.com"}, requests_stub)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Exception):
                mod.Auth0AuthVerifier()


if __name__ == "__main__":
    unittest.main()
