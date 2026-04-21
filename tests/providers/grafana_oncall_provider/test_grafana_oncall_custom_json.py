"""Unit tests for Grafana OnCall provider custom_json support."""

import json
from unittest.mock import MagicMock, patch

import pytest

from keep.providers.grafana_oncall_provider.grafana_oncall_provider import (
    GrafanaOncallProvider,
)


@pytest.fixture
def provider():
    """Create a GrafanaOncallProvider instance with mocked dependencies."""
    context_manager = MagicMock()
    provider_id = "test-grafana-oncall"
    config = MagicMock()
    config.authentication = {
        "token": "test-token",
        "host": "https://oncall-prod-us-central-0.grafana.net/oncall/",
        "oncall_integration_link": "https://oncall-prod-us-central-0.grafana.net/oncall/integrations/v1/test-webhook/",
    }
    p = GrafanaOncallProvider(context_manager, provider_id, config)
    return p


@pytest.fixture
def mock_response():
    """Create a mock successful response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": "ok"}
    resp.raise_for_status = MagicMock()
    return resp


def test_notify_default_payload(provider, mock_response):
    """Test that _notify works with default parameters (no custom_json)."""
    with patch("requests.post", return_value=mock_response) as mock_post:
        result = provider._notify(
            title="Test Alert",
            alert_uid="test-123",
            message="Something happened",
            state="alerting",
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    sent_payload = call_kwargs.kwargs["json"]

    assert sent_payload["title"] == "Test Alert"
    assert sent_payload["alert_uid"] == "test-123"
    assert sent_payload["message"] == "Something happened"
    assert sent_payload["state"] == "alerting"
    assert "custom_json" not in sent_payload
    assert result == {"status": "ok"}


def test_notify_with_custom_json_dict(provider, mock_response):
    """Test that custom_json dict is sent directly as the payload."""
    custom_payload = {
        "alert_uid": "custom-uid-001",
        "title": "Custom Title",
        "state": "alerting",
        "my_custom_field": "custom_value",
        "extra_key": 42,
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = provider._notify(
            title="Ignored Title",
            message="Ignored message",
            custom_json=custom_payload,
        )

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload == custom_payload
    assert sent_payload["my_custom_field"] == "custom_value"
    assert sent_payload["extra_key"] == 42
    # title should NOT be the ignored one
    assert sent_payload["title"] == "Custom Title"


def test_notify_with_custom_json_string(provider, mock_response):
    """Test that custom_json as a JSON string is parsed and sent as the payload."""
    custom_str = json.dumps({
        "alert_uid": "str-uid-002",
        "title": "String Payload",
        "state": "resolved",
        "custom_note": "from string",
    })

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = provider._notify(
            title="Ignored",
            custom_json=custom_str,
        )

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["title"] == "String Payload"
    assert sent_payload["custom_note"] == "from string"
    assert sent_payload["state"] == "resolved"


def test_notify_custom_json_overrides_defaults(provider, mock_response):
    """Test that when custom_json is provided, default fields are NOT included."""
    custom_payload = {"only_this_field": "value"}

    with patch("requests.post", return_value=mock_response) as mock_post:
        provider._notify(
            title="Should be ignored",
            message="Should be ignored",
            custom_json=custom_payload,
        )

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload == {"only_this_field": "value"}
    assert "title" not in sent_payload
    assert "message" not in sent_payload


def test_notify_custom_json_none_uses_defaults(provider, mock_response):
    """Test that custom_json=None falls back to default behavior."""
    with patch("requests.post", return_value=mock_response) as mock_post:
        provider._notify(
            title="Normal Title",
            custom_json=None,
        )

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["title"] == "Normal Title"
    assert sent_payload["message"] == ""


def test_notify_custom_json_invalid_string_raises(provider):
    """Test that invalid JSON string raises an error."""
    with patch("requests.post"):
        with pytest.raises(json.JSONDecodeError):
            provider._notify(
                title="test",
                custom_json="not valid json{",
            )
