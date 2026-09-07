"""The OpenAI provider default model must support the json_schema response format.

_query passes response_format=structured_output_format (a json_schema) to
chat.completions.create. json_schema is only supported on gpt-4o-mini and later, so
gpt-3.5-turbo could not serve a structured-output call that relied on the default.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.openai_provider.openai_provider import OpenaiProvider

# gpt-3.5-turbo does not support the json_schema response format the provider sends.
UNSUPPORTED_MODEL = "gpt-3.5-turbo"


def _build_provider() -> OpenaiProvider:
    config = ProviderConfig(
        description="OpenAI Provider",
        authentication={"api_key": "test-key"},
    )
    return OpenaiProvider(ContextManager(tenant_id="test"), "openai-test", config)


def _patched_client():
    """Patch the OpenAI client so the model used in the request can be captured."""
    client = MagicMock()
    message = MagicMock()
    message.content = "ok"
    client.chat.completions.create.return_value.choices = [MagicMock(message=message)]
    return patch(
        "keep.providers.openai_provider.openai_provider.OpenAI",
        return_value=client,
    ), client


def test_default_model_is_not_the_unsupported_one():
    provider = _build_provider()
    p, client = _patched_client()
    with p:
        provider._query(prompt="hi")
    assert client.chat.completions.create.call_args.kwargs["model"] != UNSUPPORTED_MODEL


def test_default_model_supports_json_schema():
    provider = _build_provider()
    p, client = _patched_client()
    with p:
        provider._query(prompt="hi")
    assert client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"
