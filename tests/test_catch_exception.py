"""catch_exception must not raise when request.state is incomplete.

Keep's handler used to read request.state.trace_id and request.state.tenant_id
directly. Starlette State.__getattr__ raises AttributeError when the attribute
was never set, and that secondary failure discarded the original exception.
"""

import asyncio
import json
import logging

import pytest
from starlette.requests import Request

from tests.fixtures.client import test_app  # noqa: F401


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/boom",
            "raw_path": b"/boom",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 123),
            "server": ("test", 80),
        }
    )


def _invoke(app, request, exc):
    handler = app.exception_handlers[Exception]

    async def _call():
        return await handler(request, exc)

    return asyncio.run(_call())


def _body(response):
    return json.loads(response.body)


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_catch_exception_tenant_missing(db_session, test_app, caplog):
    request = _request()
    request.state.trace_id = "trace-only"
    original = RuntimeError("original-boom")
    with caplog.at_level(logging.ERROR, logger="keep.api.api"):
        response = _invoke(test_app, request, original)
    assert response.status_code == 500
    body = _body(response)
    assert body["trace_id"] == "trace-only"
    assert body["error_msg"] == "original-boom"
    assert body["message"] == "An internal server error occurred."
    assert any(record.exc_info and record.exc_info[1] is original for record in caplog.records)


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_catch_exception_both_missing(db_session, test_app, caplog):
    request = _request()
    original = RuntimeError("original-boom")
    with caplog.at_level(logging.ERROR, logger="keep.api.api"):
        response = _invoke(test_app, request, original)
    assert response.status_code == 500
    body = _body(response)
    assert body["trace_id"] is None
    assert body["error_msg"] == "original-boom"
    assert any(record.exc_info and record.exc_info[1] is original for record in caplog.records)


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_catch_exception_both_present(db_session, test_app, caplog):
    request = _request()
    request.state.trace_id = "trace-both"
    request.state.tenant_id = "tenant-both"
    original = RuntimeError("original-boom")
    with caplog.at_level(logging.ERROR, logger="keep.api.api"):
        response = _invoke(test_app, request, original)
    assert response.status_code == 500
    body = _body(response)
    assert body["trace_id"] == "trace-both"
    assert body["error_msg"] == "original-boom"
    assert any(record.exc_info and record.exc_info[1] is original for record in caplog.records)
