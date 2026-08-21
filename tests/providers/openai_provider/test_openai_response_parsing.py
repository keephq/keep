"""Tests for how the OpenAI provider parses a chat completion response.

An OpenAI-compatible backend can return HTTP 200 with an empty ``choices``
list (e.g. a content-filter block). The SDK does not raise in that case, so
the provider must not crash when it indexes into ``choices[0]``.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.openai_provider.openai_provider import OpenaiProvider
from keep.providers.models.provider_config import ProviderConfig


def _build_provider() -> OpenaiProvider:
    config = ProviderConfig(
        description="OpenAI Provider",
        authentication={"api_key": "test-key"},
    )
    return OpenaiProvider(ContextManager(tenant_id="test"), "openai-test", config)


def _completion(choices):
    response = MagicMock()
    response.choices = choices
    return response


def test_empty_choices_does_not_crash():
    provider = _build_provider()
    with patch(
        "keep.providers.openai_provider.openai_provider.OpenAI"
    ) as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = _completion(
            []
        )
        assert provider._query(prompt="hi")["response"] == ""


def test_normal_response_is_returned():
    provider = _build_provider()
    message = MagicMock()
    message.content = "hello"
    choice = MagicMock()
    choice.message = message
    with patch(
        "keep.providers.openai_provider.openai_provider.OpenAI"
    ) as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = _completion(
            [choice]
        )
        assert provider._query(prompt="hi")["response"] == "hello"
