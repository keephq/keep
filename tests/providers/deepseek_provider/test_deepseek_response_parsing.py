"""Tests for how the DeepSeek provider parses a chat completion response.

DeepSeek is accessed through the OpenAI-compatible SDK, and an
OpenAI-compatible backend can return HTTP 200 with an empty ``choices`` list
(e.g. a content-filter block). The provider must not crash when it indexes
into ``choices[0]`` in that case.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.deepseek_provider.deepseek_provider import DeepseekProvider
from keep.providers.models.provider_config import ProviderConfig


def _build_provider() -> DeepseekProvider:
    config = ProviderConfig(
        description="DeepSeek Provider",
        authentication={"api_key": "test-key"},
    )
    return DeepseekProvider(ContextManager(tenant_id="test"), "deepseek-test", config)


def _completion(choices):
    response = MagicMock()
    response.choices = choices
    return response


def test_empty_choices_does_not_crash():
    provider = _build_provider()
    with patch(
        "keep.providers.deepseek_provider.deepseek_provider.OpenAI"
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
        "keep.providers.deepseek_provider.deepseek_provider.OpenAI"
    ) as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = _completion(
            [choice]
        )
        assert provider._query(prompt="hi")["response"] == "hello"
