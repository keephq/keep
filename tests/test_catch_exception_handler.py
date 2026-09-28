"""Regression tests for the ASGI catch-all exception handler.

`catch_exception` (registered via `@app.exception_handler(Exception)` in
`keep/api/api.py`) used to read `request.state.trace_id` / `request.state.tenant_id`
directly. Starlette's `State.__getattr__` raises `AttributeError` when an attribute
was never set on the request (e.g. because the failure happened before the
middleware that assigns it ran). That secondary `AttributeError` both discarded
Keep's own log line and prevented `ServerErrorMiddleware` from re-raising the
original exception.

These tests exercise the handler directly against real `Request`/`State`
objects for the three relevant combinations of `trace_id`/`tenant_id` presence.
"""

import json

import pytest
from starlette.requests import Request

from tests.fixtures.client import test_app  # noqa: F401


def _make_request(state_kwargs):
    """Build a bare ASGI `Request` and set only the given `state` attributes."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
    }
    request = Request(scope)
    for key, value in state_kwargs.items():
        setattr(request.state, key, value)
    return request


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize(
    "state_kwargs,expected_trace_id",
    [
        # (i) tenant_id missing, trace_id present
        ({"trace_id": "trace-123"}, "trace-123"),
        # (ii) both missing
        ({}, None),
        # (iii) both present
        ({"trace_id": "trace-456", "tenant_id": "tenant-789"}, "trace-456"),
    ],
    ids=["tenant_id-missing", "both-missing", "both-present"],
)
@pytest.mark.asyncio
async def test_catch_exception_handles_incomplete_request_state(
    db_session, test_app, state_kwargs, expected_trace_id
):
    """The handler must not raise AttributeError when request.state is incomplete,
    and must still return Keep's usual JSON 500 shape."""
    handler = test_app.exception_handlers[Exception]
    request = _make_request(state_kwargs)
    exc = ValueError("boom")

    # The whole point of the fix: this must not raise AttributeError on
    # Starlette's State when trace_id/tenant_id were never set.
    response = await handler(request, exc)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["message"] == "An internal server error occurred."
    assert body["trace_id"] == expected_trace_id
    assert body["error_msg"] == "boom"
