import pytest
from keep.api.utils.alert_utils import sanitize_alert

@pytest.mark.parametrize(
    "input_data,expected_output",
    [
        ({"key": "value\x00"}, {"key": "value"}),
        ({"key": ["value1", "value\x00"]}, {"key": ["value1", "value"]}),
        ({"key": ["value1", {"key": "\x00value"}]}, {"key": ["value1", {"key": "value"}]}),
        ({"nested": {"key": "\x00value"}}, {"nested": {"key": "value"}}),
        ({"nested": {"key": "value"}}, {"nested": {"key": "value"}}),
        (None, None),
    ],
)
def test_sanitize_alert(input_data, expected_output):
    sanitized_alert = sanitize_alert(input_data)
    assert sanitized_alert == expected_output, f"Expected {expected_output}, but got {sanitized_alert}"

def test_sanitize_alert_invalid_input():
    with pytest.raises(ValueError, match="Input must be a dictionary"):
        sanitize_alert("invalid input")

    with pytest.raises(ValueError, match="Input must be a dictionary"):
        sanitize_alert(12345)

    with pytest.raises(ValueError, match="Input must be a dictionary"):
        sanitize_alert(["list", "of", "values"])
