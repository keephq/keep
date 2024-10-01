import os
from unittest.mock import patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

MOCK_TOKEN = "MOCKTOKEN"


class MockSigningKey:
    def __init__(self, key):
        self.key = key


class MockJWKClient:
    def get_signing_key_from_jwt(self, token):
        # Return a mock key. Adjust the value as needed for your tests.
        return MockSigningKey(key="mock_key")


# Function to return the mock signing key
def mock_get_signing_key_from_jwt(token):
    # Return a mock key. Adjust the value as needed for your tests.
    return MockSigningKey(key="mock_key")


def get_mock_jwt_payload(token, *args, **kwargs):
    auth_type = os.getenv("AUTH_TYPE")
    if token != MOCK_TOKEN:
        raise Exception("Invalid token")
    if auth_type == "SINGLE_TENANT":
        return {
            "tenant_id": SINGLE_TENANT_UUID,
            "keep_role": "admin",
            "email": "admin@single-tenant.com",
        }
    elif auth_type == "MULTI_TENANT":
        return {
            "keep_tenant_id": "multi-tenant-id",
            "role": "admin",
            "email": "admin@multi-tenant.com",
        }
    elif auth_type == "NO_AUTH":
        # Return a payload that represents an unauthenticated or any other state
        return {}
    else:
        # Default payload or raise an exception if needed
        return {}


@pytest.mark.parametrize(
    "test_app", ["SINGLE_TENANT", "MULTI_TENANT", "NO_AUTH"], indirect=True
)
def test_api_key_with_header(db_session, client, test_app):
    """Tests the API key authentication with the x-api-key/digest"""
    auth_type = os.getenv("AUTH_TYPE")
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key)

    # Test with valid API key
    response = client.get("/providers", headers={"x-api-key": valid_api_key})
    assert response.status_code == 200

    # Test with invalid API key
    response = client.get("/providers", headers={"x-api-key": "invalid_api_key"})
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200

    # Test with digest (valid)
    response = client.get(
        "/providers", headers={"Authorization": f"Digest {valid_api_key}"}
    )
    assert response.status_code == 200

    # Test with digest (invalid)
    response = client.get(
        "/providers", headers={"Authorization": "Digest invalid_api_key"}
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200

    # Test with digest lower
    response = client.get(
        "/providers", headers={"authorization": f"digest {valid_api_key}"}
    )
    assert response.status_code == 200

    # Test with digest lower
    response = client.get(
        "/providers", headers={"authorization": "digest invalid_api_key"}
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200


@pytest.mark.parametrize(
    "test_app", ["SINGLE_TENANT", "MULTI_TENANT", "NO_AUTH"], indirect=True
)
def test_bearer_token(db_session, client, test_app):
    """Tests the bearer token authentication"""
    auth_type = os.getenv("AUTH_TYPE")
    # Test bearer tokens
    from keep.api.core import dependencies

    # Patch the jwks client (otherwise it will be None)
    dependencies.jwks_client = MockJWKClient()
    with patch("jwt.decode", side_effect=get_mock_jwt_payload), patch(
        "jwt.PyJWKClient.get_signing_key_from_jwt",
        side_effect=mock_get_signing_key_from_jwt,
    ):
        response = client.get(
            "/providers", headers={"Authorization": f"Bearer {MOCK_TOKEN}"}
        )
        assert response.status_code == 200

        response = client.get(
            "/providers", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401 if auth_type != "NO_AUTH" else 200


@pytest.mark.parametrize(
    "test_app", ["SINGLE_TENANT", "MULTI_TENANT", "NO_AUTH"], indirect=True
)
def test_webhook_api_key(db_session, client, test_app):
    """Tests the webhook API key authentication"""
    auth_type = os.getenv("AUTH_TYPE")
    valid_api_key = "valid_api_key"
    setup_api_key(db_session, valid_api_key, role="webhook")
    response = client.post(
        "/alerts/event/grafana", json={}, headers={"x-api-key": valid_api_key}
    )
    assert response.status_code == 202

    response = client.post(
        "/alerts/event/grafana", json={}, headers={"x-api-key": "invalid_api_key"}
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"Authorization": f"Digest {valid_api_key}"},
    )
    assert response.status_code == 202

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"authorization": f"digest {valid_api_key}"},
    )
    assert response.status_code == 202

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"authorization": "digest invalid_api_key"},
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 202

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"Authorization": "digest invalid_api_key"},
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 202


# sanity check with keycloak
@pytest.mark.parametrize("test_app", ["KEYCLOAK"], indirect=True)
def test_keycloak_sanity(db_session, keycloak_client, keycloak_token, client, test_app):
    """Tests the keycloak sanity check"""
    # Use the token to make a request to the Keep API
    headers = {"Authorization": f"Bearer {keycloak_token}"}
    response = client.get("/providers", headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "test_app",
    [
        {"AUTH_TYPE": "SINGLE_TENANT", "KEEP_IMPERSONATION_ENABLED": "true"},
    ],
    indirect=True,
)
def test_api_key_impersonation_without_admin(db_session, client, test_app):
    """Tests the API key impersonation with different environment settings"""

    valid_api_key = "valid_admin_api_key"
    setup_api_key(db_session, valid_api_key, role="noc")
    response = client.get(
        "/providers",
        headers={
            "x-api-key": valid_api_key,
            "X-KEEP-USER": "testuser",
            "X-KEEP-ROLE": "noc",
        },
    )
    assert response.status_code == 401
    # check the message in the response
    assert response.json()["detail"] == "Impersonation not allowed for non-admin users"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "SINGLE_TENANT",
            "KEEP_IMPERSONATION_ENABLED": "true",
            "KEEP_IMPERSONATION_AUTO_PROVISION": "false",
        },
    ],
    indirect=True,
)
def test_api_key_impersonation_without_user_provision(db_session, client, test_app):
    """Tests the API key impersonation with different environment settings"""

    valid_api_key = "valid_admin_api_key"
    setup_api_key(db_session, valid_api_key, role="admin")
    response = client.get(
        "/providers",
        headers={
            "x-api-key": valid_api_key,
            "X-KEEP-USER": "testuser",
            "X-KEEP-ROLE": "admin",
        },
    )
    assert response.status_code == 200

    # user should not be provisioned
    response = client.get("/auth/users", headers={"x-api-key": valid_api_key})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "SINGLE_TENANT",
            "KEEP_IMPERSONATION_ENABLED": "true",
            "KEEP_IMPERSONATION_AUTO_PROVISION": "true",
        },
    ],
    indirect=True,
)
def test_api_key_impersonation_with_user_provision(db_session, client, test_app):
    """Tests the API key impersonation with different environment settings"""

    valid_api_key = "valid_admin_api_key"
    setup_api_key(db_session, valid_api_key, role="admin")
    response = client.get(
        "/providers",
        headers={
            "x-api-key": valid_api_key,
            "X-KEEP-USER": "testuser",
            "X-KEEP-ROLE": "admin",
        },
    )
    assert response.status_code == 200

    # check that the user exists now
    response = client.get("/auth/users", headers={"x-api-key": valid_api_key})
    assert response.status_code == 200
    assert response.json()[0].get("email") == "testuser"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "SINGLE_TENANT",
            "KEEP_IMPERSONATION_ENABLED": "true",
            "KEEP_IMPERSONATION_AUTO_PROVISION": "true",
        },
    ],
    indirect=True,
)
def test_api_key_impersonation_provisioned_user_cant_login(
    db_session, client, test_app
):
    """Tests the API key impersonation with different environment settings"""

    valid_api_key = "valid_admin_api_key"
    setup_api_key(db_session, valid_api_key, role="admin")
    response = client.get(
        "/providers",
        headers={
            "x-api-key": valid_api_key,
            "X-KEEP-USER": "testuser",
            "X-KEEP-ROLE": "admin",
        },
    )
    assert response.status_code == 200

    # check that the user exists now
    response = client.get("/auth/users", headers={"x-api-key": valid_api_key})
    assert response.status_code == 200
    assert response.json()[0].get("email") == "testuser"

    # try to login with the user
    response = client.post(
        "/signin",
        json={"username": "testuser", "password": ""},
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Empty password"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "OAUTH2PROXY",
            "KEEP_OAUTH2_PROXY_USER_HEADER": "x-forwarded-email",
            "KEEP_OAUTH2_PROXY_USER_ROLE": "x-forwarded-groups",
        },
    ],
    indirect=True,
)
def test_oauth_proxy(db_session, client, test_app):
    """Tests the API key impersonation with different environment settings"""
    response = client.post(
        "/auth/users",
        headers={
            "x-forwarded-email": "shahar",
            "x-forwarded-groups": "noc,admin",
        },
        json={"email": "shahar", "role": "admin"},
    )
    # admin role should be able to create users
    assert response.status_code == 200

    response = client.post(
        "/auth/users",
        headers={
            "x-forwarded-email": "shahar",
            "x-forwarded-groups": "noc",
        },
        json={"email": "shahar", "role": "admin"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "OAUTH2PROXY",
            "KEEP_OAUTH2_PROXY_USER_HEADER": "x-forwarded-email",
            "KEEP_OAUTH2_PROXY_USER_ROLE": "X-Forwarded-Groups",
            "KEEP_OAUTH2_PROXY_ADMIN_ROLE": "team-platform@example.com",
            "KEEP_OAUTH2_PROXY_NOC_ROLE": "dept-engineering-product@example.com",
            "KEEP_OAUTH2_PROXY_WEBHOOK_ROLE": "foo@example.com",
            "KEEP_OAUTH2_PROXY_AUTO_CREATE_USER": "true",
        },
    ],
    indirect=True,
)
def test_oauth_proxy2(db_session, client, test_app):
    """Tests the oauth2proxy impersonation with different environment settings"""
    response = client.post(
        "/auth/users",
        headers={
            "x-forwarded-email": "shahar",
            "x-forwarded-groups": "all@example.com,aws@example.com,dept-engineering-product@example.com,team-platform@example.com",
        },
        json={"email": "shahar", "role": "admin"},
    )
    # admin role should be able to create users, noc would fail
    assert response.status_code == 200

    response = client.post(
        "/auth/users",
        headers={
            "x-forwarded-email": "shahar",
            "x-forwarded-groups": "dept-engineering-product@example.com,foo@example.com",
        },
        json={"email": "shahar", "role": "admin"},
    )
    assert response.status_code == 403
