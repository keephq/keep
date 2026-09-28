"""The OpenAI provider must not crash on an empty choices list.

An OpenAI-compatible backend can return HTTP 200 with an empty ``choices``
list (for example a content-filter block). Reading ``choices[0]`` then raises
IndexError and takes down the whole workflow step, so the provider degrades to
an empty string instead.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.openai_provider.openai_provider import OpenaiProvider


def _build_provider() -> OpenaiProvider:
    config = ProviderConfig(
        description="OpenAI Provider",
        authentication={"api_key": "test-key"},
    )
    return OpenaiProvider(ContextManager(tenant_id="test"), "openai-test", config)


def _client_returning_no_choices():
    client = MagicMock()
    client.chat.completions.create.return_value.choices = []
    return patch(
        "keep.providers.openai_provider.openai_provider.OpenAI",
        return_value=client,
    )


def test_empty_choices_returns_empty_string_instead_of_crashing():
    provider = _build_provider()
    with _client_returning_no_choices():
        result = provider._query(prompt="hi")
    assert result == {"response": ""}
