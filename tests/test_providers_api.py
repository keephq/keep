import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlmodel import Session

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.providers_factory import ProviderConfigurationException
from keep.exceptions.provider_exception import ProviderException
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

VALID_API_KEY = "valid_api_key"


@pytest.fixture
def mock_provider_in_db(db_session: Session):
    """Create a mock provider in the database."""
    provider = Provider(
        id="test_provider_id",
        tenant_id=SINGLE_TENANT_UUID,
        name="test_provider",
        description="Test provider",
        type="mock",
        installed_by="test_user",
        installation_time=datetime.now(),
        configuration_key="test_secret_key",
        validatedScopes={},
        consumer=False,
        pulling_enabled=True,
        last_pull_time=None,
        provider_metadata={},
    )
    db_session.add(provider)
    db_session.commit()
    return provider


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
class TestInvokeProviderMethod:
    """Test cases for the invoke_provider_method endpoint."""

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_success(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test successful method invocation."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        mock_provider_instance = Mock()
        mock_provider_instance.test_method.return_value = {"result": "success"}
        mock_get_provider.return_value = mock_provider_instance

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/test_method",
            json={"param1": "value1", "param2": "value2"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 200
        assert response.json() == {"result": "success"}
        mock_provider_instance.test_method.assert_called_once_with(
            param1="value1", param2="value2"
        )

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    def test_invoke_method_provider_not_found(
        self, mock_auth_verifier, client, db_session, test_app
    ):
        """Test method invocation when provider is not found."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        # Make request with non-existent provider
        response = client.post(
            "/providers/non_existent_provider/invoke/test_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_not_found(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test method invocation when method doesn't exist on provider."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        mock_provider_instance = Mock()
        # Method doesn't exist on provider
        del mock_provider_instance.non_existent_method
        mock_get_provider.return_value = mock_provider_instance

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/non_existent_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 400
        assert "Method not found" in response.json()["detail"]

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_provider_configuration_exception(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test method invocation when provider configuration is invalid."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        # Provider factory raises configuration exception
        mock_get_provider.side_effect = ProviderConfigurationException("Invalid config")

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/test_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 400
        assert "Invalid config" in response.json()["detail"]

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_provider_method_exception(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test method invocation when provider method raises ProviderMethodException."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        mock_provider_instance = Mock()
        mock_provider_instance.test_method.side_effect = ProviderMethodException(
            "Method failed", status_code=422
        )
        mock_get_provider.return_value = mock_provider_instance

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/test_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 422
        assert "Method failed" in response.json()["detail"]

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_default_provider(
        self, mock_get_provider, mock_auth_verifier, client, db_session, test_app
    ):
        """Test method invocation with default provider (not in database)."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_provider_instance = Mock()
        mock_provider_instance.test_method.return_value = {"result": "default_success"}
        mock_get_provider.return_value = mock_provider_instance

        # Make request with default provider
        response = client.post(
            "/providers/default-test/invoke/test_method",
            json={
                "param1": "value1",
            },
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 200
        assert response.json() == {"result": "default_success"}

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_invalid_parameters(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test method invocation with invalid parameters."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        mock_provider_instance = Mock()
        mock_provider_instance.test_method.side_effect = TypeError(
            "Invalid parameter type"
        )
        mock_get_provider.return_value = mock_provider_instance

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/test_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 400
        assert "Invalid request: Invalid parameter type" in response.json()["detail"]

    @patch("keep.api.routes.providers.IdentityManagerFactory.get_auth_verifier")
    @patch("keep.api.routes.providers.SecretManagerFactory.get_secret_manager")
    @patch("keep.api.routes.providers.ProvidersFactory.get_provider")
    def test_invoke_method_provider_exception(
        self,
        mock_get_provider,
        mock_secret_manager_factory,
        mock_auth_verifier,
        client,
        mock_provider_in_db,
        db_session,
        test_app,
    ):
        """Test method invocation with invalid parameters."""
        # Setup API key
        setup_api_key(
            db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin"
        )

        # Setup mocks
        mock_auth_entity = Mock()
        mock_auth_entity.tenant_id = SINGLE_TENANT_UUID
        mock_auth_verifier.return_value = lambda: mock_auth_entity

        mock_secret_manager = Mock()
        mock_secret_manager.read_secret.return_value = {
            "authentication": {"key": "value"}
        }
        mock_secret_manager_factory.return_value = mock_secret_manager

        mock_provider_instance = Mock()
        mock_provider_instance.test_method.side_effect = ProviderException(
            "chat_id is required"
        )
        mock_get_provider.return_value = mock_provider_instance

        # Make request
        response = client.post(
            f"/providers/{mock_provider_in_db.id}/invoke/test_method",
            json={"param1": "value1"},
            headers={"x-api-key": VALID_API_KEY},
        )

        # Assertions
        assert response.status_code == 400
        assert "Invalid request: chat_id is required" in response.json()["detail"]
