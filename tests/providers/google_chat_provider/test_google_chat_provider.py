"""
Tests for the send path of the Google Chat provider.

The retry loop had no coverage, and covering it is what surfaced the failure
path: the provider gave up with "Failed to notify message after 3 attempts" and
dropped whatever Google said about the rejection.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.google_chat_provider.google_chat_provider import GoogleChatProvider
from keep.providers.models.provider_config import ProviderConfig

DEFAULT_WEBHOOK = "https://chat.googleapis.com/v1/spaces/AAAADefault/messages?key=default-key&token=default-token"


def _build_provider(**authentication) -> GoogleChatProvider:
    config = ProviderConfig(
        name="google-chat",
        description="Google Chat Output Provider",
        authentication=authentication,
    )
    return GoogleChatProvider(
        ContextManager(tenant_id="test", workflow_id="test"),
        provider_id="google-chat",
        config=config,
    )


@pytest.fixture
def sleep():
    with patch("time.sleep") as mocked_sleep:
        yield mocked_sleep


@pytest.fixture
def post():
    with patch("requests.post") as mocked_post:
        mocked_post.return_value = MagicMock(status_code=200, text="{}")
        yield mocked_post


class TestSendingAndRetries:
    def test_a_successful_send_posts_once(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_count == 1

    def test_a_transient_failure_is_retried_and_then_succeeds(self, post, sleep):
        post.side_effect = [
            requests.exceptions.ConnectionError("connection reset"),
            MagicMock(status_code=200, text="{}"),
        ]

        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_count == 2
        assert sleep.call_count == 1

    def test_a_persistent_failure_gives_up_after_three_attempts(self, post, sleep):
        post.return_value = MagicMock(status_code=503, text="service unavailable")

        with pytest.raises(
            requests.exceptions.RequestException, match="after 3 attempts"
        ):
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_count == 3
        assert sleep.call_count == 2

    def test_the_failing_response_body_reaches_the_caller(self, post, sleep):
        post.return_value = MagicMock(status_code=400, text="Invalid thread key")

        with pytest.raises(requests.exceptions.RequestException) as exc_info:
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert "status code 400" in str(exc_info.value)
        assert "Invalid thread key" in str(exc_info.value)

    def test_a_failing_response_body_is_redacted(self, post, sleep):
        post.return_value = MagicMock(
            status_code=403, text=f"forbidden for {DEFAULT_WEBHOOK}"
        )

        with pytest.raises(requests.exceptions.RequestException) as exc_info:
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert "default-key" not in str(exc_info.value)
        assert "default-token" not in str(exc_info.value)
        assert "key=<redacted>" in str(exc_info.value)

    def test_a_failing_connection_message_is_redacted(self, post, sleep):
        post.side_effect = requests.exceptions.ConnectionError(
            f"cannot connect to {DEFAULT_WEBHOOK}"
        )

        with pytest.raises(requests.exceptions.RequestException) as exc_info:
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert "default-token" not in str(exc_info.value)
        assert "token=<redacted>" in str(exc_info.value)

    def test_the_content_type_header_is_sent(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert (
            post.call_args.kwargs["headers"]["Content-Type"]
            == "application/json; charset=UTF-8"
        )

    def test_unrelated_workflow_parameters_are_ignored(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", severity="critical", fingerprint="abc123"
        )

        assert post.call_args.kwargs["json"] == {"text": "hello"}
