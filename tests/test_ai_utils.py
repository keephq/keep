import pytest

from keep.api.utils.ai_utils import (
    get_ai_temperature_kwargs,
    is_ai_temperature_disabled,
)


def test_temperature_included_by_default(monkeypatch):
    monkeypatch.delenv("KEEP_AI_DISABLE_TEMPERATURE", raising=False)
    assert is_ai_temperature_disabled() is False
    assert get_ai_temperature_kwargs() == {"temperature": 0.2}
    assert get_ai_temperature_kwargs(0.7) == {"temperature": 0.7}


@pytest.mark.parametrize("value", ["true", "True", "TRUE", " 1 ", "yes", "on"])
def test_temperature_omitted_when_disabled(monkeypatch, value):
    monkeypatch.setenv("KEEP_AI_DISABLE_TEMPERATURE", value)
    assert is_ai_temperature_disabled() is True
    assert get_ai_temperature_kwargs(0.2) == {}


@pytest.mark.parametrize("value", ["false", "0", "no", "off", ""])
def test_temperature_kept_for_falsy_values(monkeypatch, value):
    monkeypatch.setenv("KEEP_AI_DISABLE_TEMPERATURE", value)
    assert is_ai_temperature_disabled() is False
    assert get_ai_temperature_kwargs(0.2) == {"temperature": 0.2}
