"""Scope validation must survive a non-JSON error body (issue #6812).

The fix in #6813 landed without tests. These pin the three shapes
`_extract_error_detail` distinguishes, and the outcome that made #6812 a bug
rather than a cosmetic one: one endpoint answering with an empty body used to
take every other scope's verdict down with it.
"""

import json
from unittest.mock import patch

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.sentry_provider.sentry_provider import SentryProvider


def _response(status_code: int, *, json_body=None, text: str = "") -> requests.Response:
    """A real `requests.Response`, so `.ok` and `.json()` behave like the wire.

    A Mock whose `.json()` is told to raise would pass these tests against a
    `try/except` that never runs, because the mock does the raising the code is
    supposed to be provoking. Setting `_content` makes the parse real.
    """
    response = requests.Response()
    response.status_code = status_code
    if json_body is not None:
        response._content = json.dumps(json_body).encode()
        response.headers["Content-Type"] = "application/json"
    else:
        response._content = text.encode()
        response.headers["Content-Type"] = "text/html"
    return response


@pytest.fixture
def sentry_provider():
    config = ProviderConfig(
        description="Test Sentry Provider",
        authentication={
            "api_key": "test-token",
            "organization_slug": "acme",
            "project_slug": "backend",
        },
    )
    return SentryProvider(
        context_manager=ContextManager(
            tenant_id="test_tenant", workflow_id="test_workflow"
        ),
        provider_id="test_sentry_provider",
        config=config,
    )


def test_an_empty_error_body_only_fails_its_own_scope(sentry_provider):
    """#6812: Sentry answers the deprecated `/plugins/webhooks/` endpoint with a
    404 and an empty text/html body.

    The assertion is the whole dict, not just `project:write`: the defect was
    that `response.json()` raised out of `validate_scopes` entirely, so the two
    scopes that had already passed never reached the caller either.
    """
    with (
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.get",
            return_value=_response(200, json_body=[]),
        ),
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.post",
            return_value=_response(404, text=""),
        ),
    ):
        scopes = sentry_provider.validate_scopes()

    assert scopes == {
        "event:read": True,
        "project:read": True,
        "project:write": "HTTP 404",
    }


def test_a_json_detail_is_reported_verbatim(sentry_provider):
    """The case the empty-body handling must not cost: when Sentry does send a
    JSON `detail`, that text is what the user needs to see."""
    with (
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.get",
            return_value=_response(200, json_body=[]),
        ),
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.post",
            return_value=_response(
                403,
                json_body={
                    "detail": "You do not have permission to perform this action."
                },
            ),
        ),
    ):
        scopes = sentry_provider.validate_scopes()

    assert scopes["project:write"] == (
        "You do not have permission to perform this action."
    )
    assert scopes["event:read"] is True
    assert scopes["project:read"] is True


def test_a_json_object_without_detail_is_rendered_rather_than_dropped(sentry_provider):
    """A JSON error body with no `detail` key: the whole object is reported.

    `.get("detail")` alone would store `None`, which renders as a scope that
    failed for no stated reason.
    """
    with (
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.get",
            return_value=_response(401, json_body={"message": "bad token"}),
        ),
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.post",
            return_value=_response(401, json_body={"message": "bad token"}),
        ),
    ):
        scopes = sentry_provider.validate_scopes()

    assert scopes == {
        "event:read": "{'message': 'bad token'}",
        "project:read": "{'message': 'bad token'}",
        "project:write": "{'message': 'bad token'}",
    }


def test_a_json_body_that_is_not_an_object_falls_back_to_the_status(sentry_provider):
    """Valid JSON that is not a mapping -- a bare list or string -- has no
    `detail` to read, so the status code is the only thing left to report.

    Separate from the empty-body case because it takes the other path: the
    parse SUCCEEDS here and the `isinstance` check is what redirects it.
    """
    with (
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.get",
            return_value=_response(200, json_body=[]),
        ),
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.post",
            return_value=_response(500, json_body=["upstream failure"]),
        ),
    ):
        scopes = sentry_provider.validate_scopes()

    assert scopes["project:write"] == "HTTP 500"
