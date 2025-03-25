import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import SQLModel

from keep.api.core.db import engine
from keep.providers.providers_service import ProvidersService


@pytest.fixture(autouse=True)
def setup_database():
    """Setup database schema before each test"""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def temp_providers_dir():
    """Create a temporary directory for provider YAML files"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture
def sample_provider_yaml():
    """Sample provider YAML content"""
    return """
name: test-victoriametrics
type: victoriametrics
authentication:
  VMAlertHost: http://localhost
  VMAlertPort: 1234
deduplication_rules:
  test-rule:
    description: Test deduplication rule
    fingerprint_fields:
      - fingerprint
      - source
    full_deduplication: true
    ignore_fields:
      - name
"""


def test_provision_provider_from_yaml(temp_providers_dir, sample_provider_yaml, caplog):
    """Test provisioning a provider from YAML file"""
    # Set logging level to DEBUG for more information
    caplog.set_level(logging.DEBUG)

    # Create a YAML file
    provider_file = os.path.join(temp_providers_dir, "test_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(sample_provider_yaml)

    # Mock provider with proper attributes
    mock_provider = MagicMock(
        type="victoriametrics",
        id="test-provider-id",
        details={
            "name": "test-victoriametrics",
            "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        },
        validatedScopes={},
    )

    # Mock environment variables
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        with patch(
            "keep.providers.providers_service.ProvidersService.is_provider_installed",
            return_value=False,
        ), patch(
            "keep.providers.providers_service.ProvidersService.install_provider",
            return_value=mock_provider,
        ) as mock_install, patch(
            "keep.providers.providers_service.provision_deduplication_rules"
        ) as mock_provision_rules, patch(
            "keep.api.core.db.get_all_provisioned_providers", return_value=[]
        ), patch(
            "keep.providers.providers_factory.ProvidersFactory.get_installed_providers",
            return_value=[mock_provider],
        ):
            # Print out all log messages
            print("\n".join([record.getMessage() for record in caplog.records]))

            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Print out debug information
            print("Mocked install call count:", mock_install.call_count)
            print("Mocked install call args:", mock_install.call_args)
            print("Mocked provision rules call count:", mock_provision_rules.call_count)

            # Verify provider installation was called with correct parameters
            mock_install.assert_called_once()
            call_args = mock_install.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"
            assert call_args["provider_name"] == "test-victoriametrics"
            assert call_args["provider_type"] == "victoriametrics"
            assert call_args["provider_config"] == {
                "VMAlertHost": "http://localhost",
                "VMAlertPort": 1234,
            }

            # Verify deduplication rules provisioning was called
            mock_provision_rules.assert_called_once()
            call_args = mock_provision_rules.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"
            assert len(call_args["deduplication_rules"]) > 0
            rule = list(call_args["deduplication_rules"].values())[0]
            assert rule["description"] == "Test deduplication rule"
            assert rule["fingerprint_fields"] == ["fingerprint", "source"]
            assert rule["full_deduplication"] is True
            assert rule["ignore_fields"] == ["name"]


def test_skip_existing_provider(temp_providers_dir, sample_provider_yaml):
    """Test that existing providers are skipped during provisioning"""
    # Create a YAML file
    provider_file = os.path.join(temp_providers_dir, "test_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(sample_provider_yaml)

    # Mock environment variables
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        # Mock database operations to simulate existing provider
        with patch(
            "keep.providers.providers_service.ProvidersService.is_provider_installed",
            return_value=True,
        ), patch(
            "keep.providers.providers_service.ProvidersService.install_provider"
        ) as mock_install:
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was not called
            mock_install.assert_not_called()


def test_invalid_yaml_file(temp_providers_dir):
    """Test handling of invalid YAML files"""
    # Create an invalid YAML file
    provider_file = os.path.join(temp_providers_dir, "invalid_provider.yaml")
    with open(provider_file, "w") as f:
        f.write("invalid: yaml: content: -")

    # Mock environment variables
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        # Mock database operations
        with patch(
            "keep.providers.providers_service.ProvidersService.is_provider_installed",
            return_value=False,
        ), patch(
            "keep.providers.providers_service.ProvidersService.install_provider"
        ) as mock_install:
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was not called
            mock_install.assert_not_called()


def test_missing_required_fields(temp_providers_dir):
    """Test handling of YAML files with missing required fields"""
    # Create a YAML file with missing required fields
    provider_file = os.path.join(temp_providers_dir, "incomplete_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(
            """
name: test-provider
# Missing type field
authentication:
  api_key: test-key
"""
        )

    # Mock environment variables
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        # Mock database operations
        with patch(
            "keep.providers.providers_service.ProvidersService.is_provider_installed",
            return_value=False,
        ), patch(
            "keep.providers.providers_service.ProvidersService.install_provider"
        ) as mock_install:
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was not called
            mock_install.assert_not_called()
