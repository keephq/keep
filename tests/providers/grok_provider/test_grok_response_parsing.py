"""Tests for how the Grok provider parses a chat completion response.

The xAI API is OpenAI-compatible, and OpenAI-compatible backends return HTTP 200
with an empty ``choices`` list on a content-filter block. ``raise_for_status``
passes, so the provider still has to read ``choices[0]`` and must not crash.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.grok_provider.grok_provider import GrokProvider
from keep.providers.models.provider_config import ProviderConfig


def _build_provider() -> GrokProvider:
    config = ProviderConfig(
        description="Grok Provider",
        authentication={"api_key": "test-key"},
    )
    return GrokProvider(ContextManager(tenant_id="test"), "grok-test", config)


def _response(payload) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    return response


def test_empty_choices_does_not_crash():
    provider = _build_provider()
    with patch("requests.post", return_value=_response({"choices": []})):
        assert provider._query(prompt="hi")["response"] == ""


def test_missing_keys_do_not_crash():
    provider = _build_provider()
    with patch("requests.post", return_value=_response({})):
        assert provider._query(prompt="hi")["response"] == ""


def test_normal_response_is_returned():
    provider = _build_provider()
    payload = {"choices": [{"message": {"content": "hello"}}]}
    with patch("requests.post", return_value=_response(payload)):
        assert provider._query(prompt="hi")["response"] == "hello"
