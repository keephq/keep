import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


# Reuse functions from your existing test
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


# Mock classes from your existing test
class MockSigningKey:
    def __init__(self, key):
        self.key = key


class MockJWKSClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        # We need to extract the actual JWT part if it has keepActiveTenant prefix
        if token.startswith("keepActiveTenant"):
            _, token = token.split("&")

        return MockSigningKey(key=self.public_key)


def test_auth0_with_active_tenant_success(db_session, client, test_app):
    """Tests Auth0 authentication with keepActiveTenant parameter when tenant is in the token"""

    # Generate test keys
    private_key_pem, public_key_pem = generate_test_keys()

    # Create payload with multiple tenant IDs
    tenant_1 = "tenant-1"
    tenant_2 = "tenant-2"

    payload = {
        "iss": "https://test-domain.auth0.com/",
        "sub": "test-user-id",
        "aud": "test-audience",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        # Note: We're not setting keep_tenant_id here since we're using keep_tenant_ids
        "keep_tenant_ids": [{"tenant_id": tenant_1}, {"tenant_id": tenant_2}],
        "keep_role": "admin",
        "email": "test@example.com",
    }

    # Sign the JWT with our private key
    token = jwt.encode(
        payload, private_key_pem, algorithm="RS256", headers={"kid": "test-key-id"}
    )

    # Prepend the keepActiveTenant parameter to use tenant_1
    active_tenant_token = f"keepActiveTenant={tenant_1}&{token}"

    # Create a mock JWKS client with our public key
    mock_jwks_client = MockJWKSClient(public_key_pem)

    # Patch the jwks_client in the auth0_authverifier module
    from ee.identitymanager.identity_managers.auth0.auth0_authverifier import (
        jwks_client,
    )

    # Save the original to restore later
    original_jwks_client = jwks_client

    try:
        # Replace the module-level client with our mock
        import ee.identitymanager.identity_managers.auth0.auth0_authverifier

        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            mock_jwks_client
        )

        # Get the auth verifier
        auth_verifier = IdentityManagerFactory.get_auth_verifier([])

        # Call the auth verifier with our active tenant token
        result = auth_verifier(
            token=active_tenant_token, api_key=None, authorization=None, request=None
        )

        # Assert authentication was successful with the specified active tenant
        assert result is not None
        assert isinstance(result, AuthenticatedEntity)
        assert result.tenant_id == tenant_1
        assert result.email == "test@example.com"
        assert result.role == "admin"

    finally:
        # Restore the original jwks_client
        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            original_jwks_client
        )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "AUTH0",
            "AUTH0_DOMAIN": "test-domain.auth0.com",
            "AUTH0_AUDIENCE": "test-audience",
        },
    ],
    indirect=True,
)
def test_auth0_with_unauthorized_active_tenant(db_session, client, test_app):
    """Tests Auth0 authentication with keepActiveTenant parameter when tenant is NOT in the token"""

    # Generate test keys
    private_key_pem, public_key_pem = generate_test_keys()

    # Create payload with tenant IDs that don't include our target tenant
    authorized_tenant = "authorized-tenant"
    unauthorized_tenant = "unauthorized-tenant"

    payload = {
        "iss": "https://test-domain.auth0.com/",
        "sub": "test-user-id",
        "aud": "test-audience",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "keep_tenant_ids": [{"tenant_id": authorized_tenant}],
        "keep_role": "admin",
        "email": "test@example.com",
    }

    # Sign the JWT with our private key
    token = jwt.encode(
        payload, private_key_pem, algorithm="RS256", headers={"kid": "test-key-id"}
    )

    # Prepend the keepActiveTenant parameter with an unauthorized tenant
    active_tenant_token = f"keepActiveTenant={unauthorized_tenant}&{token}"

    # Create a mock JWKS client with our public key
    mock_jwks_client = MockJWKSClient(public_key_pem)

    # Patch the jwks_client in the auth0_authverifier module
    from ee.identitymanager.identity_managers.auth0.auth0_authverifier import (
        jwks_client,
    )

    # Save the original to restore later
    original_jwks_client = jwks_client

    try:
        # Replace the module-level client with our mock
        import ee.identitymanager.identity_managers.auth0.auth0_authverifier

        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            mock_jwks_client
        )

        # Get the auth verifier
        auth_verifier = IdentityManagerFactory.get_auth_verifier([])

        # Call the auth verifier with our unauthorized active tenant token
        # This should raise an HTTPException with status code 401
        with pytest.raises(HTTPException) as exc_info:
            auth_verifier(
                token=active_tenant_token,
                api_key=None,
                authorization=None,
                request=None,
            )

        # Verify that the error is what we expect
        assert exc_info.value.status_code == 401
        assert "Token does not contain the active tenant" in exc_info.value.detail

    finally:
        # Restore the original jwks_client
        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            original_jwks_client
        )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "AUTH0",
            "AUTH0_DOMAIN": "test-domain.auth0.com",
            "AUTH0_AUDIENCE": "test-audience",
        },
    ],
    indirect=True,
)
def test_auth0_switching_between_tenants(db_session, client, test_app):
    """Tests Auth0 authentication with switching between different active tenants"""

    # Generate test keys
    private_key_pem, public_key_pem = generate_test_keys()

    # Create payload with multiple tenant IDs
    tenant_1 = "tenant-1"
    tenant_2 = "tenant-2"

    payload = {
        "iss": "https://test-domain.auth0.com/",
        "sub": "test-user-id",
        "aud": "test-audience",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "keep_tenant_ids": [{"tenant_id": tenant_1}, {"tenant_id": tenant_2}],
        "keep_role": "admin",
        "email": "test@example.com",
    }

    # Sign the JWT with our private key
    token = jwt.encode(
        payload, private_key_pem, algorithm="RS256", headers={"kid": "test-key-id"}
    )

    # Create tokens for both tenants
    tenant_1_token = f"keepActiveTenant={tenant_1}&{token}"
    tenant_2_token = f"keepActiveTenant={tenant_2}&{token}"

    # Create a mock JWKS client with our public key
    mock_jwks_client = MockJWKSClient(public_key_pem)

    # Patch the jwks_client in the auth0_authverifier module
    from ee.identitymanager.identity_managers.auth0.auth0_authverifier import (
        jwks_client,
    )

    # Save the original to restore later
    original_jwks_client = jwks_client

    try:
        # Replace the module-level client with our mock
        import ee.identitymanager.identity_managers.auth0.auth0_authverifier

        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            mock_jwks_client
        )

        # Get the auth verifier
        auth_verifier = IdentityManagerFactory.get_auth_verifier([])

        # Test with tenant_1
        result_1 = auth_verifier(
            token=tenant_1_token, api_key=None, authorization=None, request=None
        )

        # Assert authentication was successful with tenant_1
        assert result_1 is not None
        assert isinstance(result_1, AuthenticatedEntity)
        assert result_1.tenant_id == tenant_1

        # Now test with tenant_2
        result_2 = auth_verifier(
            token=tenant_2_token, api_key=None, authorization=None, request=None
        )

        # Assert authentication was successful with tenant_2
        assert result_2 is not None
        assert isinstance(result_2, AuthenticatedEntity)
        assert result_2.tenant_id == tenant_2

    finally:
        # Restore the original jwks_client
        ee.identitymanager.identity_managers.auth0.auth0_authverifier.jwks_client = (
            original_jwks_client
        )
