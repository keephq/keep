"""
Tests for Vertex AI provider.
"""

import pytest
from unittest.mock import patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.vertexai_provider.vertexai_provider import VertexaiProvider


class TestVertexaiProvider:
    """Test cases for Vertex AI provider."""

    def test_provider_initialization(self):
        """Test that the provider can be initialized."""
        context_manager = ContextManager(
            tenant_id="test-tenant",
            workflow_id="test-workflow",
        )
        
        config = ProviderConfig(
            authentication={
                "project_id": "test-project",
                "location": "us-central1",
            }
        )
        
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai-test",
            config=config,
        )
        
        assert provider.PROVIDER_DISPLAY_NAME == "Vertex AI"
        assert provider.PROVIDER_CATEGORY == ["AI", "Cloud Infrastructure"]

    def test_validate_config_with_service_account(self):
        """Test config validation with service account."""
        context_manager = ContextManager(
            tenant_id="test-tenant",
            workflow_id="test-workflow",
        )
        
        service_account = '{"type": "service_account", "project_id": "test"}'
        config = ProviderConfig(
            authentication={
                "project_id": "test-project",
                "location": "us-central1",
                "service_account_json": service_account,
            }
        )
        
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai-test",
            config=config,
        )
        
        provider.validate_config()
        
        assert provider.authentication_config.project_id == "test-project"
        assert provider.authentication_config.location == "us-central1"
        assert provider.authentication_config.service_account_json == service_account

    def test_validate_config_with_env_project(self):
        """Test config validation with project from environment."""
        context_manager = ContextManager(
            tenant_id="test-tenant",
            workflow_id="test-workflow",
        )
        
        config = ProviderConfig(
            authentication={
                "location": "europe-west1",
            }
        )
        
        with patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': 'env-project'}):
            provider = VertexaiProvider(
                context_manager=context_manager,
                provider_id="vertexai-test",
                config=config,
            )
            provider.validate_config()
            
            assert provider.authentication_config.project_id == "env-project"
            assert provider.authentication_config.location == "europe-west1"

    def test_expose_method(self):
        """Test the expose method returns expected configuration."""
        context_manager = ContextManager(
            tenant_id="test-tenant",
            workflow_id="test-workflow",
        )
        
        config = ProviderConfig(
            authentication={
                "project_id": "test-project",
            }
        )
        
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai-test",
            config=config,
        )
        
        exposed = provider.expose()
        
        assert "models" in exposed
        assert "gemini-1.5-flash-001" in exposed["models"]
        assert "supported_operations" in exposed
        assert "query" in exposed["supported_operations"]

    @patch('keep.providers.vertexai_provider.vertexai_provider.vertexai')
    @patch('keep.providers.vertexai_provider.vertexai_provider.GenerativeModel')
    def test_query_method(self, mock_model_class, mock_vertexai):
        """Test the query method with mocked Vertex AI."""
        context_manager = ContextManager(
            tenant_id="test-tenant",
            workflow_id="test-workflow",
        )
        
        config = ProviderConfig(
            authentication={
                "project_id": "test-project",
                "location": "us-central1",
            }
        )
        
        # Mock the response
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        mock_response = MagicMock()
        mock_response.text = "Paris"
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 10
        mock_usage.candidates_token_count = 5
        mock_usage.total_token_count = 15
        mock_response.usage_metadata = mock_usage
        mock_model.generate_content.return_value = mock_response
        
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai-test",
            config=config,
        )
        
        result = provider._query(
            prompt="What is the capital of France?",
            model="gemini-1.5-flash-001",
        )
        
        assert result["response"] == "Paris"
        assert result["model"] == "gemini-1.5-flash-001"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15

    def test_provider_factory_loading(self):
        """Test that the provider can be loaded via the factory."""
        from keep.providers.providers_factory import ProvidersFactory
        
        # This should not raise an exception
        provider_class = ProvidersFactory.get_provider_class("vertexai")
        
        assert provider_class.__name__ == "VertexaiProvider"
