import hashlib
import importlib
import sys
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.tenant import TenantApiKey


def _mock_oidc_discovery():
    """Return a context manager that stubs OIDC discovery HTTP calls.

    Prevents real network requests to Auth0 during app startup when
    AUTH_TYPE=AUTH0 is set in tests.
    """
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jwks_uri": "https://test-domain.auth0.com/.well-known/jwks.json"
    }
    mock_resp.raise_for_status = MagicMock()
    return patch("requests.get", return_value=mock_resp)


@pytest.fixture
def test_app(monkeypatch, request, db_session):
    # Store original setup_logging function
    import keep.api.logging

    original_setup_logging = keep.api.logging.setup_logging

    # Replace with no-op function to prevent threading issues
    keep.api.logging.setup_logging = lambda: None

    try:
        monkeypatch.setenv("KEEP_USE_LIMITER", "false")
        is_auth0 = False
        # Check if request.param is a dict or a string
        if isinstance(request.param, dict):
            # Set environment variables based on the provided dictionary
            for key, value in request.param.items():
                monkeypatch.setenv(key, str(value))
            is_auth0 = request.param.get("AUTH_TYPE") == "AUTH0"
        else:
            # Old behavior for string parameters
            auth_type = request.param
            monkeypatch.setenv("AUTH_TYPE", auth_type)
            monkeypatch.setenv("KEEP_JWT_SECRET", "somesecret")

            if auth_type == "MULTI_TENANT":
                monkeypatch.setenv("AUTH0_DOMAIN", "https://auth0domain.com")

        # When AUTH_TYPE=AUTH0, the authverifier module makes a real HTTP call
        # at import time to fetch the OIDC discovery document. The mock must
        # wrap the module reload as well, because deleted route modules get
        # re-imported during reload and cascade into re-importing the verifier.
        ctx = _mock_oidc_discovery() if is_auth0 else nullcontext()
        with ctx:
            # Clear and reload modules to ensure environment changes are reflected
            for module in list(sys.modules):
                if module.startswith("keep.api.routes"):
                    del sys.modules[module]

                # Bug in db patching
                elif module.startswith("keep.providers.providers_service"):
                    importlib.reload(sys.modules[module])

            if "keep.api.api" in sys.modules:
                importlib.reload(sys.modules["keep.api.api"])

            if "keep.api.config" in sys.modules:
                importlib.reload(sys.modules["keep.api.config"])

            # Import and return the app instance
            from keep.api.api import get_app
            from keep.api.config import provision_resources

            provision_resources()
            app = get_app()
        return app
    finally:
        # Restore the original setup_logging function
        keep.api.logging.setup_logging = original_setup_logging


# Fixture for TestClient using the test_app fixture
@pytest.fixture
def client(test_app, db_session, monkeypatch):
    # Your existing environment setup
    monkeypatch.setenv("PUSHER_DISABLED", "true")
    monkeypatch.setenv("KEEP_DEBUG_TASKS", "true")
    monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("SQLALCHEMY_WARN_20", "1")

    with TestClient(test_app) as client:
        yield client


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
