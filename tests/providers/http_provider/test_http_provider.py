import json
from unittest.mock import MagicMock, patch

import pytest

from keep.providers.http_provider.http_provider import HttpProvider


@pytest.fixture
def provider():
    p = HttpProvider.__new__(HttpProvider)
    p.logger = MagicMock()
    p.context_manager = MagicMock()
    return p


def _mock_response(status_code=200, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(body or {})
    resp.json.return_value = body or {}
    return resp


def test_body_json_string_is_deserialised_to_dict(provider):
    """When a workflow template renders body as a JSON string it must arrive as a dict, not a double-encoded string."""
    alert_payload = {"id": "123", "name": "test-alert"}
    body_string = json.dumps(alert_payload)

    with patch("requests.post", return_value=_mock_response()) as mock_post:
        provider._query(url="http://example.com/webhook", method="POST", body=body_string)

    _, kwargs = mock_post.call_args
    assert kwargs["json"] == alert_payload
    assert isinstance(kwargs["json"], dict)


def test_body_none_becomes_empty_dict(provider):
    """None body must be normalised to an empty dict."""

    with patch("requests.post", return_value=_mock_response()) as mock_post:
        provider._query(url="http://example.com/webhook", method="POST", body=None)

    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {}


def test_body_non_json_string_passes_through(provider):
    """A plain string body that is not valid JSON must not raise and must be forwarded as-is."""

    with patch("requests.post", return_value=_mock_response()) as mock_post:
        provider._query(url="http://example.com/webhook", method="POST", body="plain text")

    _, kwargs = mock_post.call_args
    assert kwargs["json"] == "plain text"
