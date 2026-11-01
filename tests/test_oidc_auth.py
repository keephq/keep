import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identity_managers.oidc import oidc_authverifier
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from tests.fixtures.client import client, test_app  # noqa

OIDC_ENV = {
    "AUTH_TYPE": "OIDC",
    "KEEP_OIDC_ISSUER": "https://idp.example.com",
    "KEEP_OIDC_CLIENT_ID": "keep",
    "KEEP_OIDC_ADMIN_ROLES": "keep-admins",
    "KEEP_OIDC_NOC_ROLES": "keep-noc",
    "KEEP_OIDC_WEBHOOK_ROLES": "keep-webhooks",
}


def generate_test_keys():
    # Generate private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Get the private key in PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Get the public key in PEM format
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
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


def _make_token(
    private_pem,
    groups=None,
    issuer="https://idp.example.com",
    aud="keep",
    exp_offset=3600,
    groups_claim="groups",
    include_email=True,
):
    payload = {
        "iss": issuer,
        "sub": "user-123",
        "aud": aud,
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    if include_email:
        payload["email"] = "user@keep.local"
        payload["preferred_username"] = "user"
    if groups is not None:
        payload[groups_claim] = groups
    return jwt.encode(
        payload, private_pem, algorithm="RS256", headers={"kid": "test-key-id"}
    )


def _patch_jwks_client(monkeypatch, public_pem):
    monkeypatch.setattr(
        oidc_authverifier,
        "_get_jwks_client",
        lambda issuer, jwks_url=None: (
            "https://idp.example.com/jwks",
            MockJWKSClient(public_pem),
        ),
    )


def _get_verifier():
    return IdentityManagerFactory.get_auth_verifier([])


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_valid_token_admin_group(db_session, client, test_app, monkeypatch):
    """Valid id_token with an admin group -> authenticated as admin + JIT user creation"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins", "everyone"])

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert isinstance(result, AuthenticatedEntity)
    assert result.tenant_id == SINGLE_TENANT_UUID
    assert result.email == "user@keep.local"
    assert result.role == "admin"

    from keep.api.core.db import user_exists

    assert user_exists(tenant_id=SINGLE_TENANT_UUID, username="user@keep.local")


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_groups_as_comma_separated_string(
    db_session, client, test_app, monkeypatch
):
    """Providers may send groups as a comma separated string"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups="everyone, keep-noc")

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert result.role == "noc"


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_role_priority_admin_over_noc(db_session, client, test_app, monkeypatch):
    """A user in both admin and noc groups gets the higher priority role"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-noc", "keep-admins"])

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert result.role == "admin"


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_no_mapped_group_403(db_session, client, test_app, monkeypatch):
    """A user without any mapped group is rejected with 403 (no default role)"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["everyone"])

    with pytest.raises(HTTPException) as excinfo:
        _get_verifier()(token=token, api_key=None, authorization=None, request=None)

    assert excinfo.value.status_code == 403

    from keep.api.core.db import user_exists

    assert not user_exists(tenant_id=SINGLE_TENANT_UUID, username="user@keep.local")


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_invalid_issuer_401(db_session, client, test_app, monkeypatch):
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(
        private_pem, groups=["keep-admins"], issuer="https://evil.example.com"
    )

    with pytest.raises(HTTPException) as excinfo:
        _get_verifier()(token=token, api_key=None, authorization=None, request=None)

    assert excinfo.value.status_code == 401


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_invalid_audience_401(db_session, client, test_app, monkeypatch):
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins"], aud="account")

    with pytest.raises(HTTPException) as excinfo:
        _get_verifier()(token=token, api_key=None, authorization=None, request=None)

    assert excinfo.value.status_code == 401


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_expired_token_401(db_session, client, test_app, monkeypatch):
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins"], exp_offset=-120)

    with pytest.raises(HTTPException) as excinfo:
        _get_verifier()(token=token, api_key=None, authorization=None, request=None)

    assert excinfo.value.status_code == 401


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **OIDC_ENV,
            "KEEP_OIDC_GROUPS_CLAIM": "roles",
        },
    ],
    indirect=True,
)
def test_oidc_custom_groups_claim(db_session, client, test_app, monkeypatch):
    """The groups claim name is configurable (KEEP_OIDC_GROUPS_CLAIM)"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins"], groups_claim="roles")

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert result.role == "admin"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **OIDC_ENV,
            "KEEP_OIDC_AUDIENCE": "keep-api",
        },
    ],
    indirect=True,
)
def test_oidc_audience_override(db_session, client, test_app, monkeypatch):
    """KEEP_OIDC_AUDIENCE overrides the default aud=client_id (access token mode)"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins"], aud="keep-api")

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert result.role == "admin"


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_username_fallback(db_session, client, test_app, monkeypatch):
    """Without email, preferred_username (then sub) is used as the username"""
    private_pem, public_pem = generate_test_keys()
    _patch_jwks_client(monkeypatch, public_pem)

    token = _make_token(private_pem, groups=["keep-admins"], include_email=False)

    result = _get_verifier()(
        token=token, api_key=None, authorization=None, request=None
    )

    assert result.email == "user-123"


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_discovery_cached_per_issuer(db_session, client, test_app, monkeypatch):
    """The verifier is instantiated per route, so the discovery document must be
    fetched only once per issuer (regression test for keep issue #6781)."""
    private_pem, public_pem = generate_test_keys()

    oidc_authverifier._jwks_clients.clear()

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jwks_uri": "https://idp.example.com/jwks"}
    mock_resp.raise_for_status = MagicMock()

    fake_client = MockJWKSClient(public_pem)
    with patch("requests.get", return_value=mock_resp) as mock_get:
        with patch.object(jwt, "PyJWKClient", return_value=fake_client) as mock_pyjwk:
            _uri_a, client_a = oidc_authverifier._get_jwks_client(
                "https://idp.example.com"
            )
            _uri_b, client_b = oidc_authverifier._get_jwks_client(
                "https://idp.example.com"
            )

    assert mock_get.call_count == 1
    assert mock_pyjwk.call_count == 1
    assert client_a is client_b

    oidc_authverifier._jwks_clients.clear()


@pytest.mark.parametrize("test_app", [OIDC_ENV], indirect=True)
def test_oidc_missing_env_raises(db_session, client, test_app, monkeypatch):
    """Verifier construction without issuer/client id fails fast"""
    from keep.identitymanager.identity_managers.oidc import oidc_authverifier as module

    monkeypatch.delenv("KEEP_OIDC_ISSUER")
    # drop any cached client so __init__ really validates configuration
    module._jwks_clients.clear()
    with pytest.raises(Exception, match="KEEP_OIDC_ISSUER"):
        _get_verifier()
    module._jwks_clients.clear()
