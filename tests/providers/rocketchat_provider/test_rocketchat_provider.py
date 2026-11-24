"""
Tests for the Rocket.Chat provider's webhook payload construction.

The provider only builds a payload and POSTs it, so these tests pin the
behaviour that is easy to break silently: optional fields must be omitted
rather than sent empty, and a failed POST must raise instead of logging.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.rocketchat_provider.rocketchat_provider import RocketchatProvider

WEBHOOK_URL = "https://rocketchat.example.com/hooks/abc/def"


def _build_provider() -> RocketchatProvider:
    config = ProviderConfig(
        description="Rocket.Chat Output Provider",
        authentication={"webhook_url": WEBHOOK_URL},
    )
    return RocketchatProvider(
        ContextManager(tenant_id="test"), "rocketchat-test", config
    )


def _ok_response():
    response = MagicMock()
    response.ok = True
    response.text = ""
    return response


class TestNotifyPayload:
    def test_message_only_sends_text_and_nothing_else(self):
        provider = _build_provider()
        with patch("requests.post", return_value=_ok_response()) as post:
            provider.notify(message="disk is full")

        _, kwargs = post.call_args
        assert kwargs["json"] == {"text": "disk is full"}

    def test_posts_to_configured_webhook_url(self):
        provider = _build_provider()
        with patch("requests.post", return_value=_ok_response()) as post:
            provider.notify(message="hello")

        args, _ = post.call_args
        assert args[0] == WEBHOOK_URL

    def test_optional_fields_are_included_when_set(self):
        provider = _build_provider()
        with patch("requests.post", return_value=_ok_response()) as post:
            provider.notify(
                message="hello",
                channel="#alerts",
                alias="Keep",
                emoji=":ghost:",
                avatar="https://example.com/a.png",
            )

        _, kwargs = post.call_args
        assert kwargs["json"] == {
            "text": "hello",
            "channel": "#alerts",
            "alias": "Keep",
            "emoji": ":ghost:",
            "avatar": "https://example.com/a.png",
        }

    def test_message_falls_back_to_first_attachment_text(self):
        provider = _build_provider()
        attachments = [{"text": "from attachment"}]
        with patch("requests.post", return_value=_ok_response()) as post:
            provider.notify(attachments=attachments)

        _, kwargs = post.call_args
        assert kwargs["json"]["text"] == "from attachment"
        assert kwargs["json"]["attachments"] == attachments

    def test_attachments_given_as_json_string_are_parsed(self):
        provider = _build_provider()
        with patch("requests.post", return_value=_ok_response()) as post:
            provider.notify(message="hello", attachments='[{"text": "parsed"}]')

        _, kwargs = post.call_args
        assert kwargs["json"]["attachments"] == [{"text": "parsed"}]


class TestNotifyErrors:
    def test_missing_message_and_attachments_raises(self):
        provider = _build_provider()
        with patch("requests.post") as post:
            with pytest.raises(ProviderException):
                provider.notify()

        post.assert_not_called()

    def test_failed_response_raises(self):
        provider = _build_provider()
        response = MagicMock()
        response.ok = False
        response.text = "invalid channel"
        with patch("requests.post", return_value=response):
            with pytest.raises(ProviderException) as excinfo:
                provider.notify(message="hello")

        assert "invalid channel" in str(excinfo.value)
