import pytest

from keep.api.core import dependencies


class FakePusher:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def pusher_env(monkeypatch):
    monkeypatch.setattr(dependencies, "Pusher", FakePusher)
    monkeypatch.setenv("PUSHER_APP_ID", "1")
    monkeypatch.setenv("PUSHER_APP_KEY", "test-key")
    monkeypatch.setenv("PUSHER_APP_SECRET", "test-secret")
    monkeypatch.delenv("PUSHER_DISABLED", raising=False)
    monkeypatch.delenv("PUSHER_USE_SSL", raising=False)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("false", False),
        ("False", False),
        ("0", False),
        ("true", True),
        ("True", True),
        ("1", True),
    ],
)
def test_pusher_use_ssl_parsed_from_string(pusher_env, monkeypatch, value, expected):
    """PUSHER_USE_SSL is always a string when set via docker-compose/k8s env."""
    monkeypatch.setenv("PUSHER_USE_SSL", value)
    client = dependencies.get_pusher_client()
    assert client is not None
    assert client.kwargs["ssl"] is expected


def test_pusher_use_ssl_defaults_to_false(pusher_env):
    client = dependencies.get_pusher_client()
    assert client is not None
    assert client.kwargs["ssl"] is False


@pytest.mark.parametrize("value", ["yes", "on", "not-a-bool", ""])
def test_pusher_use_ssl_unrecognized_value_keeps_ssl_enabled(
    pusher_env, monkeypatch, value
):
    """Any set-but-unrecognized value enabled SSL before the fix, so keep
    SSL on (fail-secure) instead of silently downgrading to plaintext."""
    monkeypatch.setenv("PUSHER_USE_SSL", value)
    client = dependencies.get_pusher_client()
    assert client is not None
    assert client.kwargs["ssl"] is True
