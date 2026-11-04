"""
Tests for the Google Chat provider.

The provider used to read the webhook URL from its configuration only, so a
space could only be addressed by standing up one provider per space. It now
takes a `webhook_url` per notification, which means it also has to keep the
promise that comes with accepting a caller-supplied address: only Google Chat
is ever contacted, and the URL never reaches the logs, since it carries the
`key` and `token` credentials in its query string.
"""

import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.google_chat_provider.google_chat_provider import GoogleChatProvider
from keep.providers.models.provider_config import ProviderConfig

DEFAULT_WEBHOOK = "https://chat.googleapis.com/v1/spaces/AAAADefault/messages?key=default-key&token=default-token"
OTHER_WEBHOOK = "https://chat.googleapis.com/v1/spaces/AAAAOther/messages?key=other-key&token=other-token"
WEBHOOK_URLS = {"platform": DEFAULT_WEBHOOK, "network": OTHER_WEBHOOK}


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


class TestWebhookUrlResolution:
    def test_configured_webhook_url_is_the_default(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_args.args[0] == DEFAULT_WEBHOOK

    def test_notify_webhook_url_overrides_the_default(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", webhook_url=OTHER_WEBHOOK
        )

        assert post.call_args.args[0] == OTHER_WEBHOOK

    def test_provider_validates_without_a_webhook_url(self):
        provider = _build_provider()

        assert provider.authentication_config.webhook_url is None

    def test_notify_webhook_url_is_enough_on_its_own(self, post):
        _build_provider().notify(message="hello", webhook_url=OTHER_WEBHOOK)

        assert post.call_args.args[0] == OTHER_WEBHOOK

    def test_no_target_anywhere_raises(self, post):
        with pytest.raises(ProviderException, match="No space to post to"):
            _build_provider().notify(message="hello")

        post.assert_not_called()


class TestSpaceLookup:
    def test_space_resolves_through_the_configured_map(self, post):
        _build_provider(webhook_urls=WEBHOOK_URLS).notify(
            message="hello", space="network"
        )

        assert post.call_args.args[0] == OTHER_WEBHOOK

    def test_map_can_be_given_as_a_json_string(self, post):
        _build_provider(webhook_urls=json.dumps(WEBHOOK_URLS)).notify(
            message="hello", space="network"
        )

        assert post.call_args.args[0] == OTHER_WEBHOOK

    def test_space_wins_over_the_configured_default(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK, webhook_urls=WEBHOOK_URLS).notify(
            message="hello", space="network"
        )

        assert post.call_args.args[0] == OTHER_WEBHOOK

    def test_explicit_webhook_url_wins_over_space(self, post):
        _build_provider(webhook_urls=WEBHOOK_URLS).notify(
            message="hello", space="network", webhook_url=DEFAULT_WEBHOOK
        )

        assert post.call_args.args[0] == DEFAULT_WEBHOOK

    def test_unknown_space_raises(self, post):
        with pytest.raises(ProviderException, match="Unknown space missing"):
            _build_provider(webhook_urls=WEBHOOK_URLS).notify(
                message="hello", space="missing"
            )

        post.assert_not_called()

    def test_space_without_a_map_raises(self, post):
        with pytest.raises(ProviderException, match="no webhook_urls configured"):
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
                message="hello", space="network"
            )

        post.assert_not_called()

    def test_the_map_never_reaches_the_error(self, post):
        with pytest.raises(ProviderException) as exc_info:
            _build_provider(webhook_urls=WEBHOOK_URLS).notify(
                message="hello", space="missing"
            )

        assert "default-token" not in str(exc_info.value)
        assert "other-token" not in str(exc_info.value)


class TestWebhookUrlsValidation:
    def test_malformed_json_is_rejected_at_config_time(self):
        with pytest.raises(ProviderException, match="not valid JSON"):
            _build_provider(webhook_urls="{not json")

    def test_non_object_json_is_rejected_at_config_time(self):
        with pytest.raises(ProviderException, match="must be a JSON object"):
            _build_provider(webhook_urls=json.dumps(["a", "b"]))

    def test_non_string_url_is_rejected_at_config_time(self):
        with pytest.raises(ProviderException, match="must be a webhook URL string"):
            _build_provider(webhook_urls={"network": {"url": OTHER_WEBHOOK}})

    def test_foreign_host_in_the_map_is_rejected_at_config_time(self):
        with pytest.raises(ProviderException, match="Refusing to send a message to"):
            _build_provider(
                webhook_urls={
                    "network": "https://evil.example.com/v1/spaces/A/messages"
                }
            )

    def test_empty_url_in_the_map_is_rejected_at_config_time(self):
        with pytest.raises(ProviderException, match="only https is allowed"):
            _build_provider(webhook_urls={"network": ""})

    def test_an_empty_json_object_is_allowed(self):
        provider = _build_provider(webhook_url=DEFAULT_WEBHOOK, webhook_urls="{}")

        assert provider.webhook_urls == {}

    def test_an_empty_map_is_allowed(self):
        provider = _build_provider(webhook_url=DEFAULT_WEBHOOK)

        assert provider.webhook_urls == {}


class TestWebhookUrlValidation:
    @pytest.mark.parametrize(
        "webhook_url",
        [
            "https://evil.example.com/v1/spaces/AAAA/messages",
            "https://chat.googleapis.com.evil.example.com/v1/spaces/AAAA/messages",
            "https://chat.googleapis.com:8443/v1/spaces/AAAA/messages",
            "https://user:password@chat.googleapis.com/v1/spaces/AAAA/messages",
        ],
    )
    def test_foreign_host_raises(self, post, webhook_url):
        with pytest.raises(ProviderException, match="Refusing to send a message to"):
            _build_provider().notify(message="hello", webhook_url=webhook_url)

        post.assert_not_called()

    def test_userinfo_is_not_echoed_back(self, post):
        with pytest.raises(ProviderException) as exc_info:
            _build_provider().notify(
                message="hello",
                webhook_url="https://user:password@chat.googleapis.com/v1/spaces/AAAA/messages",
            )

        assert "password" not in str(exc_info.value)

    def test_plain_http_raises(self, post):
        with pytest.raises(ProviderException, match="only https is allowed"):
            _build_provider().notify(
                message="hello",
                webhook_url="http://chat.googleapis.com/v1/spaces/AAAA/messages",
            )

        post.assert_not_called()

    def test_redirects_are_not_followed(self, post):
        _build_provider().notify(message="hello", webhook_url=DEFAULT_WEBHOOK)

        assert post.call_args.kwargs["allow_redirects"] is False


class TestPayload:
    def test_message_is_sent_as_text(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_args.kwargs["json"] == {"text": "hello"}

    def test_cards_v2_is_sent_on_its_own(self, post):
        cards = [{"cardId": "alert", "card": {"header": {"title": "Alert"}}}]

        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(cards_v2=cards)

        assert post.call_args.kwargs["json"] == {"cardsV2": cards}

    def test_message_and_cards_v2_are_sent_together(self, post):
        cards = [{"cardId": "alert", "card": {"header": {"title": "Alert"}}}]

        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", cards_v2=cards
        )

        assert post.call_args.kwargs["json"] == {"text": "hello", "cardsV2": cards}

    def test_empty_message_without_cards_v2_raises(self, post):
        with pytest.raises(ProviderException, match="Either message or cards_v2"):
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify()

        post.assert_not_called()


class TestThreading:
    def test_thread_key_is_sent_in_the_body(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", thread_key="alert-fingerprint"
        )

        assert post.call_args.kwargs["json"]["thread"] == {
            "threadKey": "alert-fingerprint"
        }

    def test_thread_key_adds_the_reply_option_and_keeps_the_credentials(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", thread_key="alert-fingerprint"
        )

        query = parse_qs(urlparse(post.call_args.args[0]).query)
        assert query["messageReplyOption"] == ["REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"]
        assert query["key"] == ["default-key"]
        assert query["token"] == ["default-token"]

    def test_no_thread_key_leaves_the_url_alone(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert post.call_args.args[0] == DEFAULT_WEBHOOK


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


class TestMechanicsTogether:
    def test_space_lookup_and_threading(self, post):
        _build_provider(webhook_urls=WEBHOOK_URLS).notify(
            message="hello", space="network", thread_key="alert-fingerprint"
        )

        sent_url = post.call_args.args[0]
        query = parse_qs(urlparse(sent_url).query)
        assert urlparse(sent_url).path == urlparse(OTHER_WEBHOOK).path
        assert query["token"] == ["other-token"]
        assert query["messageReplyOption"] == ["REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"]
        assert post.call_args.kwargs["json"]["thread"] == {
            "threadKey": "alert-fingerprint"
        }

    def test_space_lookup_and_cards(self, post):
        cards = [{"cardId": "alert", "card": {"header": {"title": "Alert"}}}]

        _build_provider(webhook_urls=WEBHOOK_URLS).notify(
            space="platform", cards_v2=cards
        )

        assert post.call_args.args[0] == DEFAULT_WEBHOOK
        assert post.call_args.kwargs["json"] == {"cardsV2": cards}

    def test_threading_on_a_url_without_a_query_string(self, post):
        bare = "https://chat.googleapis.com/v1/spaces/AAAABare/messages"

        _build_provider().notify(
            message="hello", webhook_url=bare, thread_key="alert-fingerprint"
        )

        assert post.call_args.args[0] == (
            bare + "?messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        )

    def test_an_empty_cards_v2_is_not_a_body(self, post):
        with pytest.raises(ProviderException, match="Either message or cards_v2"):
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(cards_v2=[])

        post.assert_not_called()

    def test_an_explicit_none_webhook_url_falls_back_to_the_default(self, post):
        _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(
            message="hello", webhook_url=None
        )

        assert post.call_args.args[0] == DEFAULT_WEBHOOK


class TestCredentialsAreNotLogged:
    def test_request_failure_is_logged_without_the_credentials(
        self, post, sleep, caplog
    ):
        post.side_effect = requests.exceptions.ConnectionError(
            f"Failed to establish a new connection to {DEFAULT_WEBHOOK}"
        )

        with pytest.raises(Exception):
            _build_provider(webhook_url=DEFAULT_WEBHOOK).notify(message="hello")

        assert "default-key" not in caplog.text
        assert "default-token" not in caplog.text
        assert "key=<redacted>" in caplog.text

    def test_an_unexpected_path_logs_a_placeholder_space(self, post, caplog):
        provider = _build_provider()

        with caplog.at_level("DEBUG", logger=provider.provider_id):
            provider.notify(message="hello", webhook_url="https://chat.googleapis.com/")

        assert any(
            getattr(record, "space", None) == "unknown" for record in caplog.records
        )

    def test_space_is_logged_instead_of_the_url(self, post, caplog):
        # the provider pins its own log level on init, so build it first
        provider = _build_provider(webhook_url=DEFAULT_WEBHOOK)

        with caplog.at_level("DEBUG", logger=provider.provider_id):
            provider.notify(message="hello")

        assert "default-token" not in caplog.text
        assert any(
            getattr(record, "space", None) == "AAAADefault" for record in caplog.records
        )
