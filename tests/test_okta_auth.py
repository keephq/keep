"""Tests for Okta auth verifier: group-to-role mapping, userinfo enrichment, and user auto-provisioning."""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

MOCK_TOKEN = "mock.okta.token"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OKTA_ENV = {
    "OKTA_ISSUER": "https://okta.example.com",
    "OKTA_AUDIENCE": "api://default",
    "OKTA_CLIENT_ID": "client123",
    "OKTA_CLIENT_SECRET": "secret",
    "OKTA_DOMAIN": "okta.example.com",
}


def _make_verifier(extra_env: dict | None = None, monkeypatch=None):
    """Instantiate OktaAuthVerifier with mocked JWKS client."""
    env = {**OKTA_ENV, **(extra_env or {})}
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    # Remove cached modules so env vars are picked up fresh
    for mod in list(sys.modules.keys()):
        if "okta" in mod.lower() or "keep.api.core.config" in mod:
            sys.modules.pop(mod, None)

    from keep.identitymanager.identity_managers.okta.okta_authverifier import OktaAuthVerifier

    verifier = OktaAuthVerifier.__new__(OktaAuthVerifier)
    verifier.scopes = []

    mock_jwks = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = "mock_key"
    mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("jwt.PyJWKClient", return_value=mock_jwks):
        verifier.__init__()

    return verifier


# ---------------------------------------------------------------------------
# _get_userinfo
# ---------------------------------------------------------------------------


def test_get_userinfo_returns_claims(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)
    verifier.userinfo_url = "https://okta.example.com/v1/userinfo"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "email": "user@example.com",
        "name": "John Doe",
        "groups": ["Keep_Admin", "Everyone"],
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = verifier._get_userinfo(MOCK_TOKEN)

    mock_get.assert_called_once_with(
        "https://okta.example.com/v1/userinfo",
        headers={"Authorization": f"Bearer {MOCK_TOKEN}"},
        timeout=5,
    )
    assert result["name"] == "John Doe"
    assert result["groups"] == ["Keep_Admin", "Everyone"]


def test_get_userinfo_returns_empty_on_error(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)
    verifier.userinfo_url = "https://okta.example.com/v1/userinfo"

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("requests.get", return_value=mock_resp):
        result = verifier._get_userinfo(MOCK_TOKEN)

    assert result == {}


def test_get_userinfo_returns_empty_when_no_url(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)
    verifier.userinfo_url = None

    with patch("requests.get") as mock_get:
        result = verifier._get_userinfo(MOCK_TOKEN)

    mock_get.assert_not_called()
    assert result == {}


def test_get_userinfo_returns_empty_on_exception(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)
    verifier.userinfo_url = "https://okta.example.com/v1/userinfo"

    with patch("requests.get", side_effect=ConnectionError("timeout")):
        result = verifier._get_userinfo(MOCK_TOKEN)

    assert result == {}


# ---------------------------------------------------------------------------
# Group mappings loading
# ---------------------------------------------------------------------------


def test_group_mappings_loaded_from_env(monkeypatch):
    verifier = _make_verifier(
        extra_env={
            "OKTA_ADMIN_GROUPS": "Keep_Admin,Ops_Admin",
            "OKTA_NOC_GROUPS": "Keep_User",
            "OKTA_WEBHOOK_GROUPS": "Keep_Webhook",
        },
        monkeypatch=monkeypatch,
    )
    assert verifier.group_mappings["Keep_Admin"] == "admin"
    assert verifier.group_mappings["Ops_Admin"] == "admin"
    assert verifier.group_mappings["Keep_User"] == "noc"
    assert verifier.group_mappings["Keep_Webhook"] == "webhook"


def test_group_mappings_empty_when_not_configured(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)
    assert verifier.group_mappings == {}


# ---------------------------------------------------------------------------
# Role resolution from groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "groups, expected_role",
    [
        (["Keep_Admin", "Keep_User"], "admin"),   # admin wins over noc
        (["Keep_User"], "noc"),
        (["Keep_Webhook"], "webhook"),
        (["Keep_User", "Keep_Webhook"], "noc"),   # noc wins over webhook
        ([], "noc"),                               # default role
        (["Unknown_Group"], "noc"),                # unmapped group → default
    ],
)
def test_role_resolution_priority(monkeypatch, groups, expected_role):
    verifier = _make_verifier(
        extra_env={
            "OKTA_ADMIN_GROUPS": "Keep_Admin",
            "OKTA_NOC_GROUPS": "Keep_User",
            "OKTA_WEBHOOK_GROUPS": "Keep_Webhook",
        },
        monkeypatch=monkeypatch,
    )

    jwt_payload = {
        "sub": "user@example.com",
        "email": "user@example.com",
    }
    userinfo = {"email": "user@example.com", "name": "Test User", "groups": groups}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=True),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_last_sign_in"),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_role"),
    ):
        mock_key.return_value.key = "mock_key"
        entity = verifier._verify_bearer_token(MOCK_TOKEN)

    assert entity.role == expected_role


def test_explicit_keep_role_claim_overrides_groups(monkeypatch):
    """keep_role in JWT always takes priority over group mapping."""
    verifier = _make_verifier(
        extra_env={"OKTA_ADMIN_GROUPS": "Keep_Admin", "OKTA_NOC_GROUPS": "Keep_User"},
        monkeypatch=monkeypatch,
    )

    jwt_payload = {
        "sub": "user@example.com",
        "email": "user@example.com",
        "keep_role": "webhook",  # explicit override
    }
    userinfo = {"email": "user@example.com", "groups": ["Keep_Admin"]}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=True),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_last_sign_in"),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_role"),
    ):
        mock_key.return_value.key = "mock_key"
        entity = verifier._verify_bearer_token(MOCK_TOKEN)

    assert entity.role == "webhook"


# ---------------------------------------------------------------------------
# User auto-provisioning
# ---------------------------------------------------------------------------


def test_user_created_on_first_login(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)

    jwt_payload = {"sub": "newuser@example.com", "email": "newuser@example.com"}
    userinfo = {"email": "newuser@example.com", "name": "New User", "groups": []}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=False) as mock_exists,
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.create_user") as mock_create,
    ):
        mock_key.return_value.key = "mock_key"
        verifier._verify_bearer_token(MOCK_TOKEN)

    mock_exists.assert_called_once()
    mock_create.assert_called_once_with(
        tenant_id="keep",
        username="newuser@example.com",
        password="",
        role="noc",
    )


def test_user_updated_on_subsequent_login(monkeypatch):
    verifier = _make_verifier(
        extra_env={"OKTA_ADMIN_GROUPS": "Keep_Admin"},
        monkeypatch=monkeypatch,
    )

    jwt_payload = {"sub": "existing@example.com", "email": "existing@example.com"}
    userinfo = {"email": "existing@example.com", "name": "Existing User", "groups": ["Keep_Admin"]}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=True),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.create_user") as mock_create,
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_last_sign_in") as mock_last_sign_in,
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_role") as mock_update_role,
    ):
        mock_key.return_value.key = "mock_key"
        verifier._verify_bearer_token(MOCK_TOKEN)

    mock_create.assert_not_called()
    mock_last_sign_in.assert_called_once()
    mock_update_role.assert_called_once_with(tenant_id="keep", username="existing@example.com", role="admin")


def test_auto_create_disabled(monkeypatch):
    verifier = _make_verifier(
        extra_env={"OKTA_AUTO_CREATE_USER": "false"},
        monkeypatch=monkeypatch,
    )

    jwt_payload = {"sub": "newuser@example.com", "email": "newuser@example.com"}
    userinfo = {"email": "newuser@example.com", "groups": []}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=False),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.create_user") as mock_create,
    ):
        mock_key.return_value.key = "mock_key"
        verifier._verify_bearer_token(MOCK_TOKEN)

    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# Name / email extraction
# ---------------------------------------------------------------------------


def test_name_comes_from_userinfo(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)

    jwt_payload = {"sub": "user@example.com", "email": "user@example.com"}
    userinfo = {"email": "user@example.com", "name": "Jane Doe", "groups": []}

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=True),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_last_sign_in"),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_role"),
    ):
        mock_key.return_value.key = "mock_key"
        entity = verifier._verify_bearer_token(MOCK_TOKEN)

    assert entity.name == "Jane Doe"


def test_name_falls_back_to_email_when_absent(monkeypatch):
    verifier = _make_verifier(monkeypatch=monkeypatch)

    jwt_payload = {"sub": "user@example.com", "email": "user@example.com"}
    userinfo = {"email": "user@example.com", "groups": []}  # no name

    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", return_value=jwt_payload),
        patch.object(verifier, "_get_userinfo", return_value=userinfo),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.user_exists", return_value=True),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_last_sign_in"),
        patch("keep.identitymanager.identity_managers.okta.okta_authverifier.update_user_role"),
    ):
        mock_key.return_value.key = "mock_key"
        entity = verifier._verify_bearer_token(MOCK_TOKEN)

    assert entity.name == "user@example.com"


# ---------------------------------------------------------------------------
# Token errors
# ---------------------------------------------------------------------------


def test_missing_token_raises_401(monkeypatch):
    from fastapi import HTTPException

    verifier = _make_verifier(monkeypatch=monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        verifier._verify_bearer_token("")
    assert exc_info.value.status_code == 401


def test_expired_token_raises_401(monkeypatch):
    import jwt as pyjwt
    from fastapi import HTTPException

    verifier = _make_verifier(monkeypatch=monkeypatch)
    with (
        patch.object(verifier.jwks_client, "get_signing_key_from_jwt") as mock_key,
        patch("jwt.decode", side_effect=pyjwt.ExpiredSignatureError),
    ):
        mock_key.return_value.key = "mock_key"
        with pytest.raises(HTTPException) as exc_info:
            verifier._verify_bearer_token(MOCK_TOKEN)
    assert exc_info.value.status_code == 401
