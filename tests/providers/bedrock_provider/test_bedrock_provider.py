import json
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.bedrock_provider.bedrock_provider import BedrockProvider
from keep.providers.models.provider_config import ProviderConfig


def _make_provider():
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "region": "us-east-1",
            "access_key": "test_key",
            "secret_access_key": "test_secret",
        },
    )
    return BedrockProvider(context_manager, "bedrock", config)


def _mock_invoke_response(body_dict):
    """Build a mock boto3 invoke_model response."""
    body_bytes = json.dumps(body_dict).encode()
    stream = MagicMock()
    stream.read.return_value = body_bytes
    return {"body": stream}


def test_query_claude():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _mock_invoke_response(
        {"content": [{"text": "production"}]}
    )

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = provider._query(
            prompt="Classify this alert",
            model="anthropic.claude-3-haiku-20240307-v1:0",
        )

    assert result == {"response": "production"}
    call_args = mock_client.invoke_model.call_args
    sent_body = json.loads(call_args.kwargs["body"])
    assert "messages" in sent_body
    assert sent_body["messages"][0]["content"] == "Classify this alert"


def test_query_llama():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _mock_invoke_response(
        {"generation": "staging"}
    )

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = provider._query(
            prompt="Classify this alert",
            model="meta.llama3-8b-instruct-v1:0",
        )

    assert result == {"response": "staging"}


def test_query_titan():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _mock_invoke_response(
        {"results": [{"outputText": "development"}]}
    )

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = provider._query(
            prompt="Classify this alert",
            model="amazon.titan-text-express-v1",
        )

    assert result == {"response": "development"}


def test_query_structured_output():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = _mock_invoke_response(
        {"content": [{"text": '{"environment": "production"}'}]}
    )

    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "env",
            "schema": {
                "type": "object",
                "properties": {"environment": {"type": "string"}},
                "required": ["environment"],
            },
        },
    }

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = provider._query(
            prompt="Classify",
            model="anthropic.claude-3-haiku-20240307-v1:0",
            structured_output_format=schema,
        )

    assert result == {"response": {"environment": "production"}}


def test_query_client_error():
    from botocore.exceptions import ClientError

    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "bad model"}},
        "InvokeModel",
    )

    with patch.object(provider, "_get_client", return_value=mock_client):
        try:
            provider._query(prompt="test", model="bad-model")
            assert False, "Should have raised"
        except Exception as e:
            assert "ValidationException" in str(e)


def test_iam_role_auth():
    """When no access_key/secret, boto3 should use IAM role (no explicit creds)."""
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={"region": "us-east-1"},
    )
    provider = BedrockProvider(context_manager, "bedrock", config)

    with patch("keep.providers.bedrock_provider.bedrock_provider.boto3") as mock_boto3:
        mock_boto3.client.return_value = MagicMock()
        client = provider._get_client()
        mock_boto3.client.assert_called_once_with(
            "bedrock-runtime", region_name="us-east-1"
        )
