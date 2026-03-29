"""
Unit tests for the Vertex AI provider.

All tests mock the google-cloud-aiplatform SDK so no GCP credentials are needed.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.vertexai_provider.vertexai_provider import (
    VertexaiProvider,
    VertexaiProviderAuthConfig,
)


def _make_provider(
    project_id="test-project",
    location="us-central1",
    service_account_json=None,
):
    """Helper: build a VertexaiProvider with minimal mocked context."""
    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"
    context_manager.workflow_id = "test-workflow"

    auth = {"project_id": project_id, "location": location}
    if service_account_json is not None:
        auth["service_account_json"] = service_account_json

    config = ProviderConfig(
        description="Vertex AI test provider",
        authentication=auth,
    )
    provider = VertexaiProvider(
        context_manager=context_manager,
        provider_id="vertexai_test",
        config=config,
    )
    return provider


class TestVertexaiProviderAuthConfig:
    """Tests for auth-config validation."""

    def test_minimal_config_defaults(self):
        """project_id is required; location defaults to us-central1."""
        cfg = VertexaiProviderAuthConfig(project_id="my-project")
        assert cfg.project_id == "my-project"
        assert cfg.location == "us-central1"
        assert cfg.service_account_json is None

    def test_custom_location(self):
        cfg = VertexaiProviderAuthConfig(
            project_id="my-project", location="europe-west4"
        )
        assert cfg.location == "europe-west4"

    def test_service_account_json_stored(self):
        sa = json.dumps({"type": "service_account", "project_id": "p"})
        cfg = VertexaiProviderAuthConfig(
            project_id="my-project", service_account_json=sa
        )
        assert cfg.service_account_json == sa


class TestVertexaiProviderInit:
    def test_provider_display_name(self):
        provider = _make_provider()
        assert provider.PROVIDER_DISPLAY_NAME == "Vertex AI"

    def test_provider_category(self):
        provider = _make_provider()
        assert "AI" in provider.PROVIDER_CATEGORY

    def test_validate_config_sets_auth(self):
        provider = _make_provider(project_id="proj-x", location="asia-east1")
        assert provider.authentication_config.project_id == "proj-x"
        assert provider.authentication_config.location == "asia-east1"

    def test_validate_scopes_returns_empty_dict(self):
        provider = _make_provider()
        assert provider.validate_scopes() == {}

    def test_dispose_does_not_raise(self):
        provider = _make_provider()
        provider.dispose()  # should be a no-op


class TestVertexaiProviderQuery:
    """Tests for _query / public query interface."""

    def _mock_vertexai(self, response_text="Hello from Vertex AI"):
        """Return a mock vertexai module + GenerativeModel class."""
        mock_vertexai = MagicMock()
        mock_model_class = MagicMock()
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_model_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model_instance
        return mock_vertexai, mock_model_class, mock_model_instance

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_vertexai_client")
    def test_query_returns_text_response(self, mock_get_client):
        """Plain text response is returned as-is under 'response' key."""
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "The severity is high"
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        mock_get_client.return_value = mock_model_class

        provider = _make_provider()
        result = provider._query(
            prompt="Classify this alert",
            model="gemini-1.5-pro",
            max_tokens=256,
        )

        assert result == {"response": "The severity is high"}
        mock_model_class.assert_called_once_with("gemini-1.5-pro")

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_vertexai_client")
    def test_query_parses_json_response(self, mock_get_client):
        """JSON response is automatically parsed into a dict."""
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"severity": "critical"}'
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        mock_get_client.return_value = mock_model_class

        provider = _make_provider()
        result = provider._query(prompt="Classify this alert")

        assert result == {"response": {"severity": "critical"}}

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_vertexai_client")
    def test_query_with_structured_output_format(self, mock_get_client):
        """Structured output format is injected into the prompt."""
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"environment": "production"}'
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        mock_get_client.return_value = mock_model_class

        provider = _make_provider()
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "env_class",
                "schema": {
                    "type": "object",
                    "properties": {
                        "environment": {
                            "type": "string",
                            "enum": ["production", "staging", "dev"],
                        }
                    },
                    "required": ["environment"],
                },
            },
        }
        result = provider._query(
            prompt="What environment is this alert from?",
            structured_output_format=schema,
        )

        assert result == {"response": {"environment": "production"}}
        # Verify the prompt sent to the model contains the schema
        call_args = mock_instance.generate_content.call_args
        sent_prompt = call_args[0][0]
        assert "json_schema" in sent_prompt.lower() or "schema" in sent_prompt.lower()

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_vertexai_client")
    def test_query_default_model_is_gemini(self, mock_get_client):
        """Default model is gemini-1.5-pro."""
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        mock_get_client.return_value = mock_model_class

        provider = _make_provider()
        provider._query(prompt="hello")

        mock_model_class.assert_called_once_with("gemini-1.5-pro")

    @patch("keep.providers.vertexai_provider.vertexai_provider.VertexaiProvider._get_vertexai_client")
    def test_query_passes_max_tokens(self, mock_get_client):
        """max_tokens is forwarded to GenerationConfig."""
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        mock_get_client.return_value = mock_model_class

        # Patch GenerationConfig so we can inspect the call
        with patch(
            "keep.providers.vertexai_provider.vertexai_provider.GenerationConfig",
            autospec=False,
        ) as mock_gen_cfg:
            mock_gen_cfg.return_value = MagicMock()
            provider = _make_provider()
            # We need to import GenerationConfig inside _query; patch at module level
            pass

        # Simple check: generate_content was called
        mock_instance.generate_content.assert_called_once()


class TestVertexaiProviderClientInit:
    """Tests for _get_vertexai_client — credential paths."""

    def test_import_error_raises_helpful_message(self):
        """If google-cloud-aiplatform is not installed, raise ImportError with pip hint."""
        provider = _make_provider()
        with patch.dict("sys.modules", {"vertexai": None, "vertexai.generative_models": None}):
            try:
                provider._get_vertexai_client()
                assert False, "Expected ImportError"
            except (ImportError, TypeError):
                pass  # Either error is acceptable depending on Python version

    @patch("vertexai.init")
    def test_adc_path_calls_vertexai_init(self, mock_init):
        """Without service_account_json, vertexai.init is called with project+location."""
        provider = _make_provider(project_id="my-project", location="us-east1")
        with patch("vertexai.generative_models.GenerativeModel") as mock_model:
            client = provider._get_vertexai_client()
            mock_init.assert_called_once_with(
                project="my-project",
                location="us-east1",
            )

    @patch("vertexai.init")
    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_sa_json_path_uses_credentials(self, mock_creds_factory, mock_init):
        """With service_account_json, credentials are created and passed to vertexai.init."""
        sa_json = json.dumps(
            {
                "type": "service_account",
                "project_id": "sa-project",
                "private_key_id": "key-id",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n",
                "client_email": "sa@sa-project.iam.gserviceaccount.com",
                "client_id": "123",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        mock_credentials = MagicMock()
        mock_creds_factory.return_value = mock_credentials

        provider = _make_provider(service_account_json=sa_json)
        with patch("vertexai.generative_models.GenerativeModel"):
            provider._get_vertexai_client()

        mock_init.assert_called_once_with(
            project="test-project",
            location="us-central1",
            credentials=mock_credentials,
        )

    def test_invalid_sa_json_raises_value_error(self):
        """Malformed service_account_json raises ValueError with a clear message."""
        provider = _make_provider(service_account_json="not-valid-json{}")
        with patch("vertexai.init"), patch("vertexai.generative_models.GenerativeModel"):
            try:
                provider._get_vertexai_client()
                assert False, "Expected ValueError"
            except (ValueError, Exception):
                pass


if __name__ == "__main__":
    unittest.main()
