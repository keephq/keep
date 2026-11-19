"""The DeepSeek provider must not crash on an empty choices list.

DeepSeek is reached through the OpenAI client against a different base URL, so
it shares the same failure mode: an HTTP 200 with an empty ``choices`` list
(for example a content-filter block) makes ``choices[0]`` raise IndexError and
kills the workflow step. The provider degrades to an empty string instead.
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


def _client_returning_no_choices():
    client = MagicMock()
    client.chat.completions.create.return_value.choices = []
    return patch(
        "keep.providers.deepseek_provider.deepseek_provider.OpenAI",
        return_value=client,
    )


def test_empty_choices_returns_empty_string_instead_of_crashing():
    provider = _build_provider()
    with _client_returning_no_choices():
        result = provider._query(prompt="hi")
    assert result == {"response": ""}
