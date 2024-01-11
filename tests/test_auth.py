import hashlib
import importlib
import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.tenant import TenantApiKey

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


@pytest.fixture
def test_app(monkeypatch, request):
    auth_type = request.param
    monkeypatch.setenv("AUTH_TYPE", auth_type)
    # Ok this is bit complex so stay with me:
    #   We need to reload the app to make sure the AuthVerifier is instantiated with the correct environment variable
    #   However, we can't just reload the module because the app is instantiated in the get_app() function
    #    So we need to delete the module from sys.modules and re-import it

    # First, delete all the routes modules from sys.modules
    for module in list(sys.modules):
        if module.startswith("keep.api.routes"):
            del sys.modules[module]
    # Second, delete the api module from sys.modules
    if "keep.api.api" in sys.modules:
        importlib.reload(sys.modules["keep.api.api"])

    # Now, import it, and it will re-instantiate the app with the correct environment variable
    from keep.api.api import get_app

    # Finally, return the app
    app = get_app()
    return app


# Fixture for TestClient using the test_app fixture
@pytest.fixture
def client(test_app, db_session, monkeypatch):
    # disable pusher
    monkeypatch.setenv("PUSHER_DISABLED", "true")
    return TestClient(test_app)


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


# Common setup for tests
def setup_api_key(
    db_session, api_key_value, tenant_id=SINGLE_TENANT_UUID, role="admin"
):
    hash_api_key = hashlib.sha256(api_key_value.encode()).hexdigest()
    db_session.add(
        TenantApiKey(
            tenant_id=tenant_id,
            reference_id="test_api_key",
            key_hash=hash_api_key,
            created_by="admin@keephq",
            role=role,
        )
    )
    db_session.commit()


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
    assert response.status_code == 200

    response = client.post(
        "/alerts/event/grafana", json={}, headers={"x-api-key": "invalid_api_key"}
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"Authorization": f"Digest {valid_api_key}"},
    )
    assert response.status_code == 200

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"authorization": f"digest {valid_api_key}"},
    )
    assert response.status_code == 200

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"authorization": "digest invalid_api_key"},
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200

    response = client.post(
        "/alerts/event/grafana",
        json={},
        headers={"Authorization": "digest invalid_api_key"},
    )
    assert response.status_code == 401 if auth_type != "NO_AUTH" else 200
