from keep.api.core.dependencies import parse_env_bool


def test_parse_env_bool_treats_false_strings_as_false():
    assert parse_env_bool("false") is False
    assert parse_env_bool("False") is False
    assert parse_env_bool("0") is False
    assert parse_env_bool("off") is False
    assert parse_env_bool("no") is False


def test_parse_env_bool_treats_truthy_strings_as_true():
    assert parse_env_bool("true") is True
    assert parse_env_bool("1") is True
    assert parse_env_bool("yes") is True
    assert parse_env_bool("on") is True


def test_parse_env_bool_uses_default_for_missing_values():
    assert parse_env_bool(None, default=False) is False
    assert parse_env_bool(None, default=True) is True
