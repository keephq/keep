"""Google Chat delivery uses a bounded HTTP transport, without live requests."""

import logging
import socket
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from keep.exceptions.provider_exception import ProviderException
from keep.providers.google_chat_provider import google_chat_provider as module


@pytest.fixture
def delivery(monkeypatch):
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("Network forbidden"))
    )
    provider = object.__new__(module.GoogleChatProvider)
    provider.authentication_config = SimpleNamespace(
        webhook_url="https://chat.googleapis.com/v1/spaces/test/messages?key=fixture&token=private"
    )
    provider.logger = logging.getLogger("test-google-chat")
    post = Mock()
    sleep = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    monkeypatch.setattr(module.time, "sleep", sleep)
    return provider, post, sleep


def response(status, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {})


def test_success_uses_bounded_connect_and_read_timeout(delivery):
    provider, post, sleep = delivery
    post.return_value = response(200)
    assert (
        provider._notify(message="test")
        == "Alert message sent to Google Chat successfully"
    )
    assert post.call_args.kwargs["timeout"] == (5, 15)
    assert post.call_args.kwargs["json"] == {"text": "test"}
    sleep.assert_not_called()


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_client_error_is_not_retried(delivery, status):
    provider, post, sleep = delivery
    post.return_value = response(status)
    with pytest.raises(ProviderException):
        provider._notify(message="test")
    assert post.call_count == 1
    sleep.assert_not_called()


def test_rate_limit_respects_retry_after_seconds(delivery):
    provider, post, sleep = delivery
    post.side_effect = [response(429, {"Retry-After": "7"}), response(200)]
    provider._notify(message="test")
    assert post.call_count == 2
    sleep.assert_called_once_with(7)


def test_rate_limit_respects_retry_after_http_date(delivery, monkeypatch):
    provider, post, sleep = delivery
    now = datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(module.time, "time", lambda: now)
    post.side_effect = [
        response(429, {"Retry-After": "Mon, 19 Oct 2026 00:00:09 GMT"}),
        response(200),
    ]
    provider._notify(message="test")
    sleep.assert_called_once_with(9)


def test_excessive_retry_after_fails_without_retrying_too_early(delivery):
    provider, post, sleep = delivery
    post.return_value = response(429, {"Retry-After": "3600"})
    with pytest.raises(ProviderException):
        provider._notify(message="test")
    assert post.call_count == 1
    sleep.assert_not_called()


def test_transient_server_errors_back_off_and_remain_bounded(delivery):
    provider, post, sleep = delivery
    post.return_value = response(503)
    with pytest.raises(ProviderException):
        provider._notify(message="test")
    assert post.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


def test_timeout_is_bounded_and_does_not_log_webhook_secret(delivery, caplog):
    provider, post, sleep = delivery
    post.side_effect = requests.exceptions.ReadTimeout(
        "https://chat.googleapis.com/v1/spaces/test/messages?token=secret-leak-sentinel"
    )
    with pytest.raises(ProviderException) as error:
        provider._notify(message="test")
    assert post.call_count == 3
    assert all(call.kwargs.get("timeout") == (5, 15) for call in post.call_args_list)
    assert "secret-leak-sentinel" not in caplog.text
    assert "secret-leak-sentinel" not in str(error.value)


def test_failure_does_not_affect_another_provider_instance(delivery):
    provider, post, sleep = delivery
    other = object.__new__(module.GoogleChatProvider)
    other.authentication_config = SimpleNamespace(
        webhook_url="https://example.invalid/external"
    )
    other.logger = provider.logger
    post.side_effect = [response(403), response(200)]
    with pytest.raises(ProviderException):
        provider._notify(message="internal")
    assert (
        other._notify(message="external")
        == "Alert message sent to Google Chat successfully"
    )
    assert post.call_count == 2
