import os
import sys
import types

os.environ.setdefault("KEEP_EXTERNAL_AI_TRANSFORMERS_URL", "http://mock-ai")
os.environ.setdefault("KEEP_EXTERNAL_AI_TRANSFORMERS_API_KEY", "mock-key")

# Mock optional cloud db connectors and pusher
if "google.cloud.sql.connector" not in sys.modules:
    g = types.ModuleType("google")
    gc = types.ModuleType("google.cloud")
    gcs = types.ModuleType("google.cloud.sql")
    gcsc = types.ModuleType("google.cloud.sql.connector")
    gcsc.Connector = object
    sys.modules["google"] = g
    sys.modules["google.cloud"] = gc
    sys.modules["google.cloud.sql"] = gcs
    sys.modules["google.cloud.sql.connector"] = gcsc

if "pusher" not in sys.modules:
    p = types.ModuleType("pusher")
    p.Pusher = object
    sys.modules["pusher"] = p

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from keep.identitymanager.identity_managers.oidc.oidc_authverifier import (
    OidcAuthVerifier,
    _discover_jwks_uri,
)


def generate_test_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


class MockSigningKey:
    def __init__(self, key):
        self.key = key


class MockJWKSClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return MockSigningKey(key=self.public_key)


def _make_token(private_pem, issuer, aud="keep"):
    payload = {
        "iss": issuer,
        "sub": "user-123",
        "aud": aud,
        "email": "user@keep.local",
        "groups": ["keep-admins"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, private_pem, algorithm="RS256", headers={"kid": "test-key"}
    )


def test_discover_jwks_uri_normalizes_trailing_slash():
    """Verify that _discover_jwks_uri strips trailing slash so no double slash appears."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jwks_uri": "https://auth.example.com/app/jwks"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        uri = _discover_jwks_uri("https://auth.example.com/app/")
        assert uri == "https://auth.example.com/app/jwks"
        mock_get.assert_called_once_with(
            "https://auth.example.com/app/.well-known/openid-configuration",
            timeout=10,
            headers={"User-Agent": "keep-api"},
        )


def test_oidc_issuer_with_trailing_slash_verifies_tokens(monkeypatch):
    """Verify that when KEEP_OIDC_ISSUER has a trailing slash, tokens with or without trailing slash verify."""
    monkeypatch.setenv("KEEP_OIDC_ISSUER", "https://auth.example.com/app/")
    monkeypatch.setenv("KEEP_OIDC_CLIENT_ID", "keep")
    monkeypatch.setenv("KEEP_OIDC_ADMIN_ROLES", "keep-admins")

    verifier = OidcAuthVerifier([])
    assert verifier.oidc_issuer == "https://auth.example.com/app/"
    assert "https://auth.example.com/app/" in verifier.allowed_issuers
    assert "https://auth.example.com/app" in verifier.allowed_issuers

    private_pem, public_pem = generate_test_keys()
    verifier.jwks_client = MockJWKSClient(public_pem)
    verifier.jwks_uri = "https://auth.example.com/app/jwks"

    with patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.user_exists",
        return_value=True,
    ), patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.update_user_last_sign_in"
    ), patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.update_user_role"
    ):
        # 1. Token issued with trailing slash (e.g. Authentik)
        token_slash = _make_token(private_pem, "https://auth.example.com/app/")
        entity1 = verifier._verify_bearer_token(token=token_slash)
        assert entity1.email == "user@keep.local"
        assert entity1.role == "admin"

        # 2. Token issued without trailing slash
        token_no_slash = _make_token(private_pem, "https://auth.example.com/app")
        entity2 = verifier._verify_bearer_token(token=token_no_slash)
        assert entity2.email == "user@keep.local"
        assert entity2.role == "admin"


def test_oidc_issuer_without_trailing_slash_verifies_tokens(monkeypatch):
    """Verify that when KEEP_OIDC_ISSUER has no trailing slash, tokens with or without trailing slash verify."""
    monkeypatch.setenv("KEEP_OIDC_ISSUER", "https://auth.example.com/app")
    monkeypatch.setenv("KEEP_OIDC_CLIENT_ID", "keep")
    monkeypatch.setenv("KEEP_OIDC_ADMIN_ROLES", "keep-admins")

    verifier = OidcAuthVerifier([])
    assert verifier.oidc_issuer == "https://auth.example.com/app"
    assert "https://auth.example.com/app/" in verifier.allowed_issuers
    assert "https://auth.example.com/app" in verifier.allowed_issuers

    private_pem, public_pem = generate_test_keys()
    verifier.jwks_client = MockJWKSClient(public_pem)
    verifier.jwks_uri = "https://auth.example.com/app/jwks"

    with patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.user_exists",
        return_value=True,
    ), patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.update_user_last_sign_in"
    ), patch(
        "keep.identitymanager.identity_managers.oidc.oidc_authverifier.update_user_role"
    ):
        # 1. Token issued with trailing slash
        token_slash = _make_token(private_pem, "https://auth.example.com/app/")
        entity1 = verifier._verify_bearer_token(token=token_slash)
        assert entity1.email == "user@keep.local"
        assert entity1.role == "admin"

        # 2. Token issued without trailing slash
        token_no_slash = _make_token(private_pem, "https://auth.example.com/app")
        entity2 = verifier._verify_bearer_token(token=token_no_slash)
        assert entity2.email == "user@keep.local"
        assert entity2.role == "admin"


def test_oidc_invalid_issuer_rejected(monkeypatch):
    """Verify that tokens from untrusted issuers are strictly rejected with 401."""
    monkeypatch.setenv("KEEP_OIDC_ISSUER", "https://auth.example.com/app")
    monkeypatch.setenv("KEEP_OIDC_CLIENT_ID", "keep")
    monkeypatch.setenv("KEEP_OIDC_ADMIN_ROLES", "keep-admins")

    verifier = OidcAuthVerifier([])
    private_pem, public_pem = generate_test_keys()
    verifier.jwks_client = MockJWKSClient(public_pem)
    verifier.jwks_uri = "https://auth.example.com/app/jwks"

    token_evil = _make_token(private_pem, "https://evil.attacker.com")
    with pytest.raises(HTTPException) as excinfo:
        verifier._verify_bearer_token(token=token_evil)
    assert excinfo.value.status_code == 401
    assert "Invalid token" in excinfo.value.detail
