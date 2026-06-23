from unittest.mock import patch

from keep.api.core.dependencies import get_pusher_client


def test_get_pusher_client_uses_false_for_string_false(monkeypatch):
    monkeypatch.setenv("PUSHER_APP_ID", "123")
    monkeypatch.setenv("PUSHER_APP_KEY", "key")
    monkeypatch.setenv("PUSHER_APP_SECRET", "secret")
    monkeypatch.setenv("PUSHER_USE_SSL", "false")

    with patch("keep.api.core.dependencies.Pusher") as mock_pusher:
        get_pusher_client()

    assert mock_pusher.call_args.kwargs["ssl"] is False


def test_get_pusher_client_uses_true_for_string_true(monkeypatch):
    monkeypatch.setenv("PUSHER_APP_ID", "123")
    monkeypatch.setenv("PUSHER_APP_KEY", "key")
    monkeypatch.setenv("PUSHER_APP_SECRET", "secret")
    monkeypatch.setenv("PUSHER_USE_SSL", "true")

    with patch("keep.api.core.dependencies.Pusher") as mock_pusher:
        get_pusher_client()

    assert mock_pusher.call_args.kwargs["ssl"] is True


def test_get_pusher_client_respects_pusher_disabled(monkeypatch):
    monkeypatch.setenv("PUSHER_DISABLED", "true")
    monkeypatch.setenv("PUSHER_APP_ID", "123")
    monkeypatch.setenv("PUSHER_APP_KEY", "key")
    monkeypatch.setenv("PUSHER_APP_SECRET", "secret")

    with patch("keep.api.core.dependencies.Pusher") as mock_pusher:
        client = get_pusher_client()

    assert client is None
    mock_pusher.assert_not_called()
