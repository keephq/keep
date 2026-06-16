from keep.api.core.dependencies import _env_flag


def test_env_flag_defaults_to_false_when_missing(monkeypatch):
    monkeypatch.delenv("PUSHER_USE_SSL", raising=False)

    assert _env_flag("PUSHER_USE_SSL") is False


def test_env_flag_parses_truthy_strings(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("PUSHER_USE_SSL", value)
        assert _env_flag("PUSHER_USE_SSL") is True


def test_env_flag_parses_falsey_strings(monkeypatch):
    for value in ("0", "false", "FALSE", "no", "off", ""):
        monkeypatch.setenv("PUSHER_USE_SSL", value)
        assert _env_flag("PUSHER_USE_SSL") is False
