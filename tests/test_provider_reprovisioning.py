import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.providers_service import ProvidersService
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory


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


def test_provider_reprovisioning_with_updated_config(
    db_session, provider_configs, caplog
):
    """
    Test that demonstrates the issue with re-provisioning a provider with new configurations but the same name.

    The test should fail because the current implementation of ProvidersService.is_provider_installed()
    prevents the updated configuration from being applied when the provider name is the same.
    """
    caplog.set_level(logging.DEBUG)
    tenant_id = SINGLE_TENANT_UUID

    # Mock the secret manager to return different configurations based on when it's called
    initial_config = {
        "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        "name": "keepVictoriaMetrics",
    }
    updated_config = {
        "authentication": {"VMAlertHost": "http://vmmetrics.com", "VMAlertPort": 1234},
        "name": "keepVictoriaMetrics",
    }

    # Create a mock secret manager that returns different values based on call count
    mock_secret_manager = MagicMock()
    mock_secret_manager.read_secret.side_effect = [initial_config, updated_config]

    mock_provider = MagicMock(spec=Provider)
    mock_provider.id = "mock-provider-id"
    mock_provider.name = "keepVictoriaMetrics"
    mock_provider.type = "victoriametrics"
    mock_provider.tenant_id = tenant_id
    mock_provider.configuration_key = f"{tenant_id}_victoriametrics_mock-provider-id"

    # Mock the install_provider method to return a valid response
    mock_install_result = {
        "type": "victoriametrics",
        "id": "mock-provider-id",
        "details": {
            "authentication": provider_configs["initial"]["keepVictoriaMetrics"][
                "authentication"
            ],
            "name": "keepVictoriaMetrics",
        },
        "validatedScopes": {},
    }

    # Step 1: Initial provisioning with mocks
    with (
        patch.dict(
            os.environ, {"KEEP_PROVIDERS": json.dumps(provider_configs["initial"])}
        ),
        patch("keep.providers.providers_service.ProvidersService.install_webhook"),
        patch.object(
            SecretManagerFactory, "get_secret_manager", return_value=mock_secret_manager
        ),
        patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]),
        patch(
            "keep.providers.providers_service.ProvidersService.install_provider",
            return_value=mock_install_result,
        ),
        patch("keep.api.core.db.get_provider_by_name", return_value=mock_provider),
    ):
        # Provision the initial provider
        ProvidersService.provision_providers(tenant_id)

        # Verify the initial configuration
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        provider_config = secret_manager.read_secret(
            mock_provider.configuration_key, is_json=True
        )

        assert (
            provider_config["authentication"]["VMAlertHost"] == "http://localhost"
        ), "Initial configuration should have localhost as host"

    # Step 2: Try to re-provision with updated configuration
    updated_mock_secret_manager = MagicMock()
    updated_mock_secret_manager.read_secret.return_value = updated_config

    # Create a direct mock for the get_provider_by_name function that will be used in the provision_providers method
    def mock_get_provider_by_name(*args, **kwargs):
        return mock_provider

    with (
        patch.dict(
            os.environ, {"KEEP_PROVIDERS": json.dumps(provider_configs["updated"])}
        ),
        patch("keep.providers.providers_service.ProvidersService.install_webhook"),
        patch.object(
            SecretManagerFactory,
            "get_secret_manager",
            return_value=updated_mock_secret_manager,
        ),
        patch(
            "keep.api.core.db.get_all_provisioned_providers",
            return_value=[mock_provider],
        ),
        patch(
            "keep.providers.providers_service.get_provider_by_name",
            side_effect=mock_get_provider_by_name,
        ),
        patch(
            "keep.providers.providers_service.ProvidersService.is_provider_installed",
            return_value=True,
        ),
        patch(
            "keep.providers.providers_service.ProvidersService.update_provider"
        ) as mock_update_provider,
    ):
        # Call provision_providers which should update the existing provider
        ProvidersService.provision_providers(tenant_id)

        # Verify that update_provider was called with the correct parameters
        mock_update_provider.assert_called_once()
        call_args = mock_update_provider.call_args[1]
        assert call_args["tenant_id"] == tenant_id
        assert call_args["provider_id"] == mock_provider.id
        assert (
            call_args["provider_info"]
            == provider_configs["updated"]["keepVictoriaMetrics"]["authentication"]
        )
        assert call_args["updated_by"] == "system"
        assert call_args["allow_provisioned"] == True

        # Verify that the configuration would be updated correctly
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        provider_config = secret_manager.read_secret(
            mock_provider.configuration_key, is_json=True
        )

        assert (
            provider_config["authentication"]["VMAlertHost"] == "http://vmmetrics.com"
        ), "Configuration should be updated to vmmetrics.com"
