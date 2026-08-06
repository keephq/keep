"""
Tests for how the LiteLLM provider parses a chat completion response.

Two failure modes this covers, both silent or misleading before the fix:

1. A reasoning model can return `content: null` when the whole `max_tokens`
   budget went into reasoning tokens. The provider returned
   `{"response": None}` and the workflow step counted as successful.
2. Models frequently wrap structured output in a ```json fence, which made
   `json.loads()` fail and killed the step even though the JSON was valid.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.litellm_provider.litellm_provider import LitellmProvider
from keep.providers.models.provider_config import ProviderConfig

SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string"}},
    "required": ["verdict"],
}


def _build_provider() -> LitellmProvider:
    config = ProviderConfig(
        description="LiteLLM Provider",
        authentication={"api_url": "https://litellm.example.com/v1"},
    )
    return LitellmProvider(ContextManager(tenant_id="test"), "litellm-test", config)


def _response(content, finish_reason="stop", usage=None, model=None):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    payload = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]
    }
    if usage is not None:
        payload["usage"] = usage
    if model is not None:
        payload["model"] = model
    response.json = MagicMock(return_value=payload)
    return response


class TestStripCodeFence:
    @pytest.mark.parametrize(
        "text",
        [
            '```json\n{"verdict": "ok"}\n```',
            '```\n{"verdict": "ok"}\n```',
            '  ```json\n{"verdict": "ok"}\n```  ',
        ],
    )
    def test_fenced_json_is_unwrapped(self, text):
        assert LitellmProvider._strip_code_fence(text) == '{"verdict": "ok"}'

    def test_plain_json_is_untouched(self):
        assert LitellmProvider._strip_code_fence('{"verdict": "ok"}') == (
            '{"verdict": "ok"}'
        )


def test_structured_output_accepts_fenced_json():
    provider = _build_provider()
    with patch(
        "requests.post", return_value=_response('```json\n{"verdict": "ok"}\n```')
    ):
        result = provider._query(prompt="hi", structured_output_format=SCHEMA)
    assert result["response"] == {"verdict": "ok"}


def test_none_content_raises_instead_of_returning_null():
    provider = _build_provider()
    with patch("requests.post", return_value=_response(None, finish_reason="length")):
        with pytest.raises(ProviderException) as excinfo:
            provider._query(prompt="hi")
    message = str(excinfo.value)
    assert "no content" in message
    assert "length" in message


def test_plain_text_response_still_works():
    provider = _build_provider()
    with patch("requests.post", return_value=_response("plain answer")):
        assert provider._query(prompt="hi")["response"] == "plain answer"


def test_usage_is_returned_alongside_the_response():
    """A workflow needs the token count and cost to report what a run spent."""
    provider = _build_provider()
    usage = {
        "prompt_tokens": 256,
        "completion_tokens": 98,
        "total_tokens": 354,
        "cost": 0.00042,
    }
    with patch(
        "requests.post", return_value=_response("hi", usage=usage, model="gpt-4o")
    ):
        result = provider._query(prompt="hi")
    assert result["response"] == "hi"
    assert result["prompt_tokens"] == 256
    assert result["completion_tokens"] == 98
    assert result["total_tokens"] == 354
    assert result["cost"] == 0.00042
    assert result["model"] == "gpt-4o"


def test_missing_usage_does_not_break_the_response():
    """Not every OpenAI-compatible backend reports usage."""
    provider = _build_provider()
    with patch("requests.post", return_value=_response("hi")):
        result = provider._query(prompt="hi", model="local-model")
    assert result["response"] == "hi"
    assert result["prompt_tokens"] is None
    assert result["cost"] is None
    assert result["model"] == "local-model"
