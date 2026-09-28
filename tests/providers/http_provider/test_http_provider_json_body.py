"""Tests for HTTP provider double-encoding a templated JSON body (issue #6547).

Bug: _query() normalises `headers` when it arrives as a string, but never does
the same for `body`. A workflow using `body: "{{ alert }}"` renders to a JSON
*string*, which was then handed to requests as `json=body` and serialised a
second time — so the receiving endpoint got a quoted string like
"\\"{\\\\\"id\\\\\": ...}\\"" instead of a JSON object.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.http_provider.http_provider import HttpProvider
from keep.providers.models.provider_config import ProviderConfig

RENDERED_ALERT = '{"id": "123", "name": "cpu high"}'
ALERT_OBJECT = {"id": "123", "name": "cpu high"}


def _build_provider() -> HttpProvider:
    config = ProviderConfig(description="HTTP Provider", authentication={})
    return HttpProvider(ContextManager(tenant_id="test"), "http-test", config)


def _response(payload, ok=True, status_code=200):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.reason = "OK"
    response.text = "body"
    response.json = MagicMock(return_value=payload)
    return response


def _call_kwargs(method, body):
    """Run a request and return the kwargs requests.<method> was called with."""
    provider = _build_provider()
    with patch(f"requests.{method.lower()}", return_value=_response({})) as request:
        provider._query(
            url="http://example.com/api",
            method=method,
            headers={"Content-Type": "application/json"},
            body=body,
        )
    return request.call_args.kwargs


class TestTemplatedJsonStringBody:
    """Bug #6547: a rendered {{ alert }} string must reach the endpoint as JSON."""

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    def test_json_string_is_parsed_before_sending(self, method):
        kwargs = _call_kwargs(method, RENDERED_ALERT)
        assert kwargs.get("json") == ALERT_OBJECT
        assert "data" not in kwargs

    def test_nested_json_string_survives(self):
        body = '{"labels": {"severity": "critical"}, "values": [1, 2]}'
        kwargs = _call_kwargs("POST", body)
        assert kwargs.get("json") == {
            "labels": {"severity": "critical"},
            "values": [1, 2],
        }


class TestExistingBehaviourIsPreserved:
    """The fix must not change how bodies already work today."""

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    def test_dict_body_unchanged(self, method):
        kwargs = _call_kwargs(method, ALERT_OBJECT)
        assert kwargs.get("json") == ALERT_OBJECT
        assert "data" not in kwargs

    def test_none_body_becomes_empty_dict(self):
        kwargs = _call_kwargs("POST", None)
        assert kwargs.get("json") == {}

    def test_list_body_unchanged(self):
        kwargs = _call_kwargs("POST", [{"a": 1}])
        assert kwargs.get("json") == [{"a": 1}]


class TestNonJsonStringBody:
    """A plain-text body must not be JSON-encoded just because it is a string."""

    def test_plain_text_is_sent_as_data(self):
        kwargs = _call_kwargs("POST", "hello world")
        assert kwargs.get("data") == "hello world"
        assert "json" not in kwargs

    def test_xml_is_sent_as_data(self):
        xml = "<alert><id>123</id></alert>"
        kwargs = _call_kwargs("POST", xml)
        assert kwargs.get("data") == xml
        assert "json" not in kwargs

    def test_bare_number_string_is_not_treated_as_json(self):
        """json.loads('123') returns an int; sending that as a body is wrong."""
        kwargs = _call_kwargs("POST", "123")
        assert kwargs.get("data") == "123"
        assert "json" not in kwargs
