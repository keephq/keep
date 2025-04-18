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
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider",
                return_value=mock_provider,
            ) as mock_install,
            patch(
                "keep.providers.providers_service.ProvidersService.provision_provider_deduplication_rules"
            ) as mock_provision_provider_rules,
            patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]),
            patch(
                "keep.providers.providers_factory.ProvidersFactory.get_installed_providers",
                return_value=[mock_provider],
            ),
        ):
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

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
            mock_provision_provider_rules.assert_called_once()
            call_args = mock_provision_provider_rules.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"
            assert "provider" in call_args
            assert "deduplication_rules" in call_args


def test_invalid_yaml_file(temp_providers_dir):
    """Test handling of invalid YAML files"""
    # Create an invalid YAML file
    provider_file = os.path.join(temp_providers_dir, "invalid_provider.yaml")
    with open(provider_file, "w") as f:
        f.write("invalid: yaml: content: -")

    # Mock environment variables
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        # Mock database operations
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider"
            ) as mock_install,
        ):
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
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider"
            ) as mock_install,
        ):
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was not called
            mock_install.assert_not_called()


def test_provider_yaml_with_multiple_deduplication_rules(temp_providers_dir, caplog):
    """Test provisioning a provider from YAML file with multiple deduplication rules"""
    yaml_content = """
name: test-victoriametrics
type: victoriametrics
authentication:
  VMAlertHost: http://localhost
  VMAlertPort: 1234
deduplication_rules:
  rule1:
    description: First deduplication rule
    fingerprint_fields:
      - fingerprint
      - source
    full_deduplication: true
    ignore_fields:
      - name
  rule2:
    description: Second deduplication rule
    fingerprint_fields:
      - alert_id
      - service
    full_deduplication: false
    ignore_fields:
      - lastReceived
"""
    # Create a YAML file
    provider_file = os.path.join(temp_providers_dir, "test_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(yaml_content)

    # Mock provider
    mock_provider = MagicMock(
        type="victoriametrics",
        id="test-provider-id",
        details={
            "name": "test-victoriametrics",
            "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        },
        validatedScopes={},
    )

    # Mock environment variables and services
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider",
                return_value=mock_provider,
            ) as mock_install,
            patch(
                "keep.providers.providers_service.ProvidersService.provision_provider_deduplication_rules"
            ) as mock_provision_provider_rules,
            patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]),
        ):
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation
            mock_install.assert_called_once()

            # Verify deduplication rules provisioning
            mock_provision_provider_rules.assert_called_once()
            call_args = mock_provision_provider_rules.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"

            rules = call_args["deduplication_rules"]
            assert len(rules) == 2

            rule1 = rules["rule1"]
            assert rule1["description"] == "First deduplication rule"
            assert rule1["fingerprint_fields"] == ["fingerprint", "source"]
            assert rule1["full_deduplication"] is True
            assert rule1["ignore_fields"] == ["name"]

            rule2 = rules["rule2"]
            assert rule2["description"] == "Second deduplication rule"
            assert rule2["fingerprint_fields"] == ["alert_id", "service"]
            assert rule2["full_deduplication"] is False
            assert rule2["ignore_fields"] == ["lastReceived"]


def test_provider_yaml_with_empty_deduplication_rules(temp_providers_dir, caplog):
    """Test provisioning a provider from YAML file with empty deduplication rules"""
    yaml_content = """
name: test-victoriametrics
type: victoriametrics
authentication:
  VMAlertHost: http://localhost
  VMAlertPort: 1234
deduplication_rules: {}
"""
    # Create a YAML file
    provider_file = os.path.join(temp_providers_dir, "test_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(yaml_content)

    # Mock provider
    mock_provider = MagicMock(
        type="victoriametrics",
        id="test-provider-id",
        details={
            "name": "test-victoriametrics",
            "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        },
        validatedScopes={},
    )

    # Mock environment variables and services
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider",
                return_value=mock_provider,
            ) as mock_install,
            patch(
                "keep.providers.providers_service.ProvidersService.provision_provider_deduplication_rules"
            ) as mock_provision_provider_rules,
            patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]),
        ):
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was called
            mock_install.assert_called_once()

            # Verify deduplication rules provisioning was called with empty rules
            mock_provision_provider_rules.assert_called_once()
            call_args = mock_provision_provider_rules.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"
            assert call_args["deduplication_rules"] == {}


def test_provider_yaml_with_invalid_deduplication_rules(temp_providers_dir, caplog):
    """Test provisioning a provider from YAML file with invalid deduplication rules"""
    yaml_content = """
name: test-victoriametrics
type: victoriametrics
authentication:
  VMAlertHost: http://localhost
  VMAlertPort: 1234
deduplication_rules:
  invalid_rule:
    # Missing required fields
    description: Invalid rule
"""
    # Create a YAML file
    provider_file = os.path.join(temp_providers_dir, "test_provider.yaml")
    with open(provider_file, "w") as f:
        f.write(yaml_content)

    # Mock provider
    mock_provider = MagicMock(
        type="victoriametrics",
        id="test-provider-id",
        details={
            "name": "test-victoriametrics",
            "authentication": {"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
        },
        validatedScopes={},
    )

    # Mock environment variables and services
    with patch.dict(os.environ, {"KEEP_PROVIDERS_DIRECTORY": temp_providers_dir}):
        with (
            patch(
                "keep.providers.providers_service.ProvidersService.is_provider_installed",
                return_value=False,
            ),
            patch(
                "keep.providers.providers_service.ProvidersService.install_provider",
                return_value=mock_provider,
            ) as mock_install,
            patch(
                "keep.providers.providers_service.ProvidersService.provision_provider_deduplication_rules"
            ) as mock_provision_provider_rules,
            patch("keep.api.core.db.get_all_provisioned_providers", return_value=[]),
            patch(
                "sqlmodel.Session",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(return_value=MagicMock()),
                        __exit__=MagicMock(),
                    )
                ),
            ),
        ):
            # Call the provisioning function
            ProvidersService.provision_providers("test-tenant")

            # Verify provider installation was called
            mock_install.assert_called_once()

            # Verify deduplication rules provisioning was called
            mock_provision_provider_rules.assert_called_once()
            call_args = mock_provision_provider_rules.call_args[1]
            assert call_args["tenant_id"] == "test-tenant"

            # Even invalid rules should be passed through, validation happens in provision_deduplication_rules
            assert len(call_args["deduplication_rules"]) == 1
            rule = call_args["deduplication_rules"]["invalid_rule"]
            assert rule["description"] == "Invalid rule"
            assert "fingerprint_fields" not in rule
