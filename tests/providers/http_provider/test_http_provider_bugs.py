"""Tests for HTTP provider result duplication (issue #6431).

Bug: HttpProvider._notify() called the public self.query() instead of the
private self._query(). BaseProvider.notify() appends to self.results after
_notify() returns, and BaseProvider.query() appends as well, so every notify()
recorded the same result twice in the workflow execution output.
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.http_provider.http_provider import HttpProvider
from keep.providers.models.provider_config import ProviderConfig


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


class TestNotifyDoesNotDuplicateResults:
    """Bug #6431: results appended twice per action execution."""

    def test_notify_appends_exactly_one_result(self):
        provider = _build_provider()
        with patch("requests.post", return_value=_response({"ok": True})):
            provider.notify(
                url="http://example.com/api", method="POST", body={"message": "Hello"}
            )
        assert len(provider.results) == 1

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    def test_no_duplication_for_any_write_method(self, method):
        provider = _build_provider()
        with patch(f"requests.{method.lower()}", return_value=_response({"ok": True})):
            provider.notify(url="http://example.com/api", method=method, body={})
        assert len(provider.results) == 1

    def test_repeated_notifies_append_one_each(self):
        """Two executions record two results, not four."""
        provider = _build_provider()
        with patch("requests.post", return_value=_response({"ok": True})):
            provider.notify(url="http://example.com/api", method="POST", body={})
            provider.notify(url="http://example.com/api", method="POST", body={})
        assert len(provider.results) == 2

    def test_notify_still_returns_the_response(self):
        """The fix must not change what notify() hands back to the workflow."""
        provider = _build_provider()
        with patch("requests.post", return_value=_response({"ok": True})):
            result = provider.notify(
                url="http://example.com/api", method="POST", body={}
            )
        assert result == {
            "status": True,
            "status_code": 200,
            "body": {"ok": True},
        }
        assert provider.results == [result]


class TestQueryStillRecordsItsOwnResult:
    """Guard: the fix must not stop query() from recording when used directly."""

    def test_query_appends_one_result(self):
        provider = _build_provider()
        with patch("requests.get", return_value=_response({"ok": True})):
            provider.query(url="http://example.com/api", method="GET")
        assert len(provider.results) == 1
