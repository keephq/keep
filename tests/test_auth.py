import hashlib
import importlib
import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.tenant import TenantApiKey


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
def client(test_app, db_session):
    return TestClient(test_app)


def get_mock_jwt_payload():
    auth_type = os.getenv("AUTH_TYPE")
    if auth_type == "SINGLE_TENANT":
        return {
            "keep_tenant_id": SINGLE_TENANT_UUID,
            "keep_role": "admin",
            "email": "admin@single-tenant.com",
        }
    elif auth_type == "MULTI_TENANT":
        return {
            "keep_tenant_id": "multi-tenant-id",
            "keep_role": "admin",
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
    "auth_type", ["SINGLE_TENANT", "MULTI_TENANT", "NO_AUTH"], indirect=True
)
def test_bearer_token(client, db_session, auth_type, monkeypatch):
    monkeypatch.setenv("AUTH_TYPE", auth_type)

    # Test with valid API key
    with patch("jwt.decode", side_effect=get_mock_jwt_payload):
        response = client.get(
            "/providers", headers={"Authorization": "Bearer MOCKTOKEN"}
        )
        assert response.status_code == 200
