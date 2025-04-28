import json
import logging
import os
from unittest.mock import patch, MagicMock

import pytest
from sqlmodel import Session, SQLModel, select

from keep.api.core.db import engine, get_provider_by_name
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_service import ProvidersService
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory


@pytest.fixture(autouse=True)
def setup_database():
    """Setup database schema before each test"""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def provider_configs():
    """Fixture for provider configurations used in tests"""
    return {
        "initial": {
            "keepVictoriaMetrics": {
                "type": "victoriametrics",
                "authentication": {
                    "VMAlertHost": "http://localhost",
                    "VMAlertPort": 1234,
                },
            }
        },
        "updated": {
            "keepVictoriaMetrics": {
                "type": "victoriametrics",
                "authentication": {
                    "VMAlertHost": "http://vmmetrics.com",
                    "VMAlertPort": 1234,
                },
            }
        },
    }


def test_provider_reprovisioning_with_updated_config(provider_configs, caplog):
    """
    Test that demonstrates the issue with re-provisioning a provider with new configurations but the same name.

    The test should fail because the current implementation of ProvidersService.is_provider_installed()
    prevents the updated configuration from being applied when the provider name is the same.
    """
    caplog.set_level(logging.DEBUG)
    tenant_id = SINGLE_TENANT_UUID

    # Mock the secret manager to return the initial configuration
    initial_config = {
        "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        "name": "keepVictoriaMetrics",
    }
    mock_secret_manager = MagicMock()
    mock_secret_manager.read_secret.return_value = initial_config

    # Step 1: Initial provisioning with mocks
    with patch.dict(
        os.environ, {"KEEP_PROVIDERS": json.dumps(provider_configs["initial"])}
    ), patch(
        "keep.providers.providers_service.ProvidersService.install_webhook"
    ), patch.object(
        SecretManagerFactory, "get_secret_manager", return_value=mock_secret_manager
    ), patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]):
        # Provision the initial provider
        ProvidersService.provision_providers(tenant_id)

        # Verify the initial provider was installed
        provider = get_provider_by_name(tenant_id, "keepVictoriaMetrics")
        assert provider is not None, "Provider should be installed"

        # Verify the initial configuration
        with Session(engine) as session:
            db_provider = session.exec(
                select(Provider).where(
                    (Provider.tenant_id == tenant_id)
                    & (Provider.name == "keepVictoriaMetrics")
                )
            ).one()

            context_manager = ContextManager(tenant_id=tenant_id)
            secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
            provider_config = secret_manager.read_secret(
                db_provider.configuration_key, is_json=True
            )

            assert (
                provider_config["authentication"]["VMAlertHost"] == "http://localhost"
            ), "Initial configuration should have localhost as host"

    # Step 2: Try to re-provision with updated configuration
    with patch.dict(
        os.environ, {"KEEP_PROVIDERS": json.dumps(provider_configs["updated"])}
    ), patch(
        "keep.providers.providers_service.ProvidersService.install_webhook"
    ), patch.object(
        SecretManagerFactory, "get_secret_manager", return_value=mock_secret_manager
    ), patch("keep.api.core.db.get_all_provisioned_providers", return_value=[provider]):
        ProvidersService.provision_providers(tenant_id)

        with Session(engine) as session:
            db_provider = session.exec(
                select(Provider).where(
                    (Provider.tenant_id == tenant_id)
                    & (Provider.name == "keepVictoriaMetrics")
                )
            ).one()

            context_manager = ContextManager(tenant_id=tenant_id)
            secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
            provider_config = secret_manager.read_secret(
                db_provider.configuration_key, is_json=True
            )

            # This assertion should fail because the configuration should be updated to "http://vmmetrics.com"
            # but the current implementation prevents it from being updated
            assert (
                provider_config["authentication"]["VMAlertHost"]
                == "http://vmmetrics.com"
            ), "Configuration should be updated to vmmetrics.com but remains localhost"
