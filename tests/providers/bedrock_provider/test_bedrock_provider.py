"""Tests for the AWS Bedrock provider."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.bedrock_provider.bedrock_provider import (
    BedrockProvider,
    BedrockProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def base_config():
    return ProviderConfig(
        description="Test Bedrock Provider",
        authentication={
            "region": "us-east-1",
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        },
    )


@pytest.fixture
def iam_config():
    """Config that relies on IAM role (no explicit credentials)."""
    return ProviderConfig(
        description="IAM-based Bedrock Provider",
        authentication={"region": "eu-west-1"},
    )


@pytest.fixture
def provider(context_manager, base_config):
    return BedrockProvider(context_manager, "test_bedrock", base_config)


@pytest.fixture
def iam_provider(context_manager, iam_config):
    return BedrockProvider(context_manager, "test_bedrock_iam", iam_config)


# ---------------------------------------------------------------------------
# Auth config tests
# ---------------------------------------------------------------------------


class TestBedrockProviderAuthConfig:
    def test_region_required(self):
        with pytest.raises(Exception):
            BedrockProviderAuthConfig()

    def test_credentials_optional(self):
        cfg = BedrockProviderAuthConfig(region="us-east-1")
        assert cfg.access_key is None
        assert cfg.secret_access_key is None
        assert cfg.session_token is None

    def test_full_credentials(self):
        cfg = BedrockProviderAuthConfig(
            region="us-west-2",
            access_key="AKIA...",
            secret_access_key="secret",
            session_token="token",
        )
        assert cfg.region == "us-west-2"
        assert cfg.access_key == "AKIA..."
        assert cfg.session_token == "token"


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_validate_config_with_credentials(self, provider):
        assert provider.authentication_config.region == "us-east-1"
        assert provider.authentication_config.access_key == "AKIAIOSFODNN7EXAMPLE"

    def test_validate_config_iam(self, iam_provider):
        assert iam_provider.authentication_config.region == "eu-west-1"
        assert iam_provider.authentication_config.access_key is None


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    @patch("boto3.client")
    def test_client_created_with_credentials(self, mock_boto3, provider):
        provider._get_client()
        mock_boto3.assert_called_once_with(
            "bedrock-runtime",
            region_name="us-east-1",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

    @patch("boto3.client")
    def test_client_created_iam(self, mock_boto3, iam_provider):
        iam_provider._get_client()
        mock_boto3.assert_called_once_with(
            "bedrock-runtime",
            region_name="eu-west-1",
        )

    @patch("boto3.client")
    def test_client_cached(self, mock_boto3, provider):
        provider._get_client()
        provider._get_client()
        assert mock_boto3.call_count == 1


# ---------------------------------------------------------------------------
# _build_request_body
# ---------------------------------------------------------------------------


class TestBuildRequestBody:
    def test_claude_body(self, provider):
        body = json.loads(
            provider._build_request_body(
                "anthropic.claude-3-sonnet-20240229-v1:0", "hello", 512, None
            )
        )
        assert "messages" in body
        assert body["messages"][0]["content"] == "hello"
        assert body["max_tokens"] == 512
        assert body["anthropic_version"] == "bedrock-2023-05-31"

    def test_claude_body_with_structured_output(self, provider):
        schema = {"type": "json_schema", "json_schema": {"name": "test", "schema": {"type": "object"}}}
        body = json.loads(
            provider._build_request_body(
                "anthropic.claude-3-haiku-20240307-v1:0", "test", 256, schema
            )
        )
        assert "system" in body
        assert "JSON" in body["system"]

    def test_llama_body(self, provider):
        body = json.loads(
            provider._build_request_body("meta.llama3-8b-instruct-v1:0", "hi", 256, None)
        )
        assert body["prompt"] == "hi"
        assert body["max_gen_len"] == 256

    def test_mistral_body(self, provider):
        body = json.loads(
            provider._build_request_body("mistral.mistral-7b-instruct-v0:2", "hi", 256, None)
        )
        assert "[INST]" in body["prompt"]
        assert body["max_tokens"] == 256

    def test_cohere_body(self, provider):
        body = json.loads(
            provider._build_request_body("cohere.command-r-v1:0", "hi", 100, None)
        )
        assert body["prompt"] == "hi"
        assert body["max_tokens"] == 100

    def test_titan_body(self, provider):
        body = json.loads(
            provider._build_request_body("amazon.titan-text-express-v1", "hi", 100, None)
        )
        assert body["inputText"] == "hi"
        assert body["textGenerationConfig"]["maxTokenCount"] == 100


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parse_claude(self, provider):
        raw = {"content": [{"text": "Hello from Claude"}]}
        assert provider._parse_response("anthropic.claude-3-sonnet-20240229-v1:0", raw) == "Hello from Claude"

    def test_parse_llama(self, provider):
        raw = {"generation": "Hello from Llama"}
        assert provider._parse_response("meta.llama3-8b-instruct-v1:0", raw) == "Hello from Llama"

    def test_parse_mistral(self, provider):
        raw = {"outputs": [{"text": "Hello from Mistral"}]}
        assert provider._parse_response("mistral.mistral-7b-instruct-v0:2", raw) == "Hello from Mistral"

    def test_parse_cohere(self, provider):
        raw = {"generations": [{"text": "Hello from Cohere"}]}
        assert provider._parse_response("cohere.command-r-v1:0", raw) == "Hello from Cohere"

    def test_parse_titan(self, provider):
        raw = {"results": [{"outputText": "Hello from Titan"}]}
        assert provider._parse_response("amazon.titan-text-express-v1", raw) == "Hello from Titan"

    def test_parse_empty_claude(self, provider):
        assert provider._parse_response("anthropic.claude-3-sonnet-20240229-v1:0", {}) == ""

    def test_parse_empty_titan(self, provider):
        assert provider._parse_response("amazon.titan-text-express-v1", {}) == ""


# ---------------------------------------------------------------------------
# _query (integration-style with mocked boto3)
# ---------------------------------------------------------------------------


def _make_mock_response(model_id: str, text: str) -> dict:
    """Build a fake invoke_model response dict for the given model."""
    model_lower = model_id.lower()
    if "anthropic.claude" in model_lower:
        payload = {"content": [{"text": text}]}
    elif "meta.llama" in model_lower:
        payload = {"generation": text}
    elif "mistral" in model_lower:
        payload = {"outputs": [{"text": text}]}
    elif "cohere" in model_lower:
        payload = {"generations": [{"text": text}]}
    else:
        payload = {"results": [{"outputText": text}]}
    return {"body": BytesIO(json.dumps(payload).encode())}


class TestQuery:
    @patch("boto3.client")
    def test_query_titan_default_model(self, mock_boto3, provider):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.invoke_model.return_value = _make_mock_response(
            BedrockProvider.DEFAULT_MODEL, "Titan response"
        )

        result = provider.query(prompt="test prompt")
        assert result["response"] == "Titan response"

    @patch("boto3.client")
    def test_query_claude(self, mock_boto3, provider):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        model = "anthropic.claude-3-haiku-20240307-v1:0"
        mock_client.invoke_model.return_value = _make_mock_response(model, "Claude response")

        result = provider.query(prompt="test", model=model)
        assert result["response"] == "Claude response"

    @patch("boto3.client")
    def test_query_with_structured_output(self, mock_boto3, provider):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        model = "anthropic.claude-3-haiku-20240307-v1:0"
        mock_client.invoke_model.return_value = _make_mock_response(
            model, '{"environment": "production"}'
        )

        result = provider.query(
            prompt="classify this alert",
            model=model,
            structured_output_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "env",
                    "schema": {
                        "type": "object",
                        "properties": {"environment": {"type": "string"}},
                    },
                },
            },
        )
        assert isinstance(result["response"], dict)
        assert result["response"]["environment"] == "production"

    @patch("boto3.client")
    def test_query_client_error_raises_provider_exception(self, mock_boto3, provider):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "InvokeModel",
        )

        with pytest.raises(ProviderException, match="AccessDeniedException"):
            provider.query(prompt="test")

    @patch("boto3.client")
    def test_query_invokes_correct_model_id(self, mock_boto3, provider):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        model = "meta.llama3-8b-instruct-v1:0"
        mock_client.invoke_model.return_value = _make_mock_response(model, "Llama!")

        provider.query(prompt="hi", model=model)
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == model

    @patch("boto3.client")
    def test_validate_scopes_returns_empty_dict(self, mock_boto3, provider):
        assert provider.validate_scopes() == {}
