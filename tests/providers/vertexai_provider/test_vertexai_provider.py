import json
import os
import pytest
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.vertexai_provider.vertexai_provider import (
    VertexaiProvider,
    VertexaiProviderAuthConfig,
)


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def api_key_config():
    return ProviderConfig(
        authentication={
            "api_key": "test-api-key",
        }
    )


@pytest.fixture
def service_account_config():
    sa_json = json.dumps({
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    return ProviderConfig(
        authentication={
            "service_account_json": sa_json,
            "project_id": "test-project",
            "region": "us-central1",
        }
    )


class TestVertexaiProviderAuthConfig:
    def test_api_key_auth(self):
        config = VertexaiProviderAuthConfig(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.service_account_json is None
        assert config.project_id is None
        assert config.region == "us-central1"

    def test_service_account_auth(self):
        config = VertexaiProviderAuthConfig(
            service_account_json='{"type": "service_account"}',
            project_id="my-project",
            region="europe-west1",
        )
        assert config.service_account_json == '{"type": "service_account"}'
        assert config.project_id == "my-project"
        assert config.region == "europe-west1"

    def test_region_options(self):
        """Test that all common Vertex AI regions are available."""
        config = VertexaiProviderAuthConfig(api_key="test")
        # Access the field metadata to verify options
        fields = VertexaiProviderAuthConfig.__dataclass_fields__
        region_options = fields["region"].metadata.get("options", [])
        assert "us-central1" in region_options
        assert "europe-west1" in region_options
        assert "asia-east1" in region_options


class TestVertexaiProviderInit:
    def test_init_with_api_key(self, context_manager, api_key_config):
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )
        assert provider.authentication_config.api_key == "test-api-key"
        assert provider.PROVIDER_DISPLAY_NAME == "Vertex AI"
        assert provider.PROVIDER_CATEGORY == ["AI"]

    def test_init_with_service_account(self, context_manager, service_account_config):
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=service_account_config,
        )
        assert provider.authentication_config.service_account_json is not None
        assert provider.authentication_config.project_id == "test-project"

    def test_validate_config_missing_auth(self, context_manager):
        config = ProviderConfig(authentication={})
        with pytest.raises(ValueError, match="Either 'api_key' or 'service_account_json'"):
            VertexaiProvider(
                context_manager=context_manager,
                provider_id="vertexai_test",
                config=config,
            )

    def test_validate_config_sa_without_project(self, context_manager):
        config = ProviderConfig(
            authentication={
                "service_account_json": '{"type": "service_account"}',
            }
        )
        with pytest.raises(ValueError, match="'project_id' is required"):
            VertexaiProvider(
                context_manager=context_manager,
                provider_id="vertexai_test",
                config=config,
            )


class TestVertexaiProviderQuery:
    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_client")
    def test_query_basic(self, mock_get_client, context_manager, api_key_config):
        """Test basic text query."""
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "4"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_get_client.return_value = mock_genai

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )

        result = provider._query(prompt="What is 2+2?", max_tokens=10)
        assert result["response"] == "4"

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_client")
    def test_query_with_model(self, mock_get_client, context_manager, api_key_config):
        """Test query with specific model."""
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Hello"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_get_client.return_value = mock_genai

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )

        result = provider._query(prompt="Say hello", model="gemini-1.5-pro")
        mock_genai.GenerativeModel.assert_called_once()
        call_kwargs = mock_genai.GenerativeModel.call_args
        assert call_kwargs[1]["model_name"] == "gemini-1.5-pro" or "gemini-1.5-pro" in str(call_kwargs)

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_client")
    def test_query_structured_output(self, mock_get_client, context_manager, api_key_config):
        """Test query with structured output format."""
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"environment": "production"}'
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_get_client.return_value = mock_genai

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )

        structured_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "environment_restoration",
                "schema": {
                    "type": "object",
                    "properties": {
                        "environment": {
                            "type": "string",
                            "enum": ["production", "debug", "pre-prod"],
                        },
                    },
                    "required": ["environment"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

        result = provider._query(
            prompt="What environment is this?",
            structured_output_format=structured_format,
        )
        assert result["response"] == {"environment": "production"}
        # Verify system instruction was set
        call_kwargs = mock_genai.GenerativeModel.call_args
        assert call_kwargs[1]["system_instruction"] is not None

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_client")
    def test_query_json_response_parsing(self, mock_get_client, context_manager, api_key_config):
        """Test that JSON responses are automatically parsed."""
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"key": "value", "number": 42}'
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_get_client.return_value = mock_genai

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )

        result = provider._query(prompt="Return JSON")
        assert isinstance(result["response"], dict)
        assert result["response"]["key"] == "value"
        assert result["response"]["number"] == 42

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_client")
    def test_query_plain_text_stays_string(self, mock_get_client, context_manager, api_key_config):
        """Test that plain text responses remain as strings."""
        mock_genai = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is just plain text, not JSON."
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_get_client.return_value = mock_genai

        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )

        result = provider._query(prompt="Say something")
        assert isinstance(result["response"], str)
        assert result["response"] == "This is just plain text, not JSON."


class TestVertexaiProviderDispose:
    def test_dispose(self, context_manager, api_key_config):
        provider = VertexaiProvider(
            context_manager=context_manager,
            provider_id="vertexai_test",
            config=api_key_config,
        )
        # dispose should not raise
        provider.dispose()
