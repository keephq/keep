import os
from unittest.mock import patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID

from tests.fixtures.client import test_app, client, setup_api_key

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
            "keep_tenant_id": SINGLE_TENANT_UUID,
            "keep_role": "admin",
            "email": "admin@single-tenant.com",
        }
    elif auth_type == "MULTI_TENANT":
        return {
            "tenant_id": "multi-tenant-id",
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
def test_api_key_with_header(client, db_session, test_app):
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
def test_bearer_token(client, db_session, test_app):
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
def test_webhook_api_key(client, db_session, test_app):
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
