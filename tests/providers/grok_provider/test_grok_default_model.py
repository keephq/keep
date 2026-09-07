"""The Grok provider default model must be one the xAI API still serves.

grok-1 is xAI's open-weights release, not a model the api.x.ai chat completions
endpoint serves, so a call that relied on the default failed model-not-found.
"""

from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.grok_provider.grok_provider import GrokProvider
from keep.providers.models.provider_config import ProviderConfig

# grok-1 is the open-weights release; the API never served it as a chat model.
RETIRED_MODEL = "grok-1"


def _build_provider() -> GrokProvider:
    config = ProviderConfig(
        description="Grok Provider",
        authentication={"api_key": "test-key"},
    )
    return GrokProvider(ContextManager(tenant_id="test"), "grok-test", config)


def _capture_post():
    """Patch requests.post and return the mock so the sent payload can be read."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(
        return_value={"choices": [{"message": {"content": "ok"}}]}
    )
    return patch("requests.post", return_value=response)


def test_default_model_is_not_the_retired_one():
    provider = _build_provider()
    with _capture_post() as post:
        provider._query(prompt="hi")
    assert post.call_args.kwargs["json"]["model"] != RETIRED_MODEL


def test_default_model_is_a_served_model():
    provider = _build_provider()
    with _capture_post() as post:
        provider._query(prompt="hi")
    assert post.call_args.kwargs["json"]["model"] == "grok-4.5"
