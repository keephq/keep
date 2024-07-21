import hashlib
import importlib
import sys

import pytest
from fastapi.testclient import TestClient

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.tenant import TenantApiKey


@pytest.fixture
def test_app(monkeypatch, request):
    auth_type = request.param
    elastic_enabled = None
    if isinstance(auth_type, tuple):
        auth_type = auth_type[0]
        elastic_enabled = auth_type[1]

    monkeypatch.setenv("AUTH_TYPE", auth_type)
    monkeypatch.setenv("KEEP_JWT_SECRET", "somesecret")
    if elastic_enabled is not None:
        monkeypatch.setenv("ELASTIC_ENABLED", str(elastic_enabled))
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
