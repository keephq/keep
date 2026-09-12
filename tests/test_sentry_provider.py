"""Sentry provider scope validation must survive non-JSON error bodies (issue #6812)."""

import json
from unittest.mock import patch

import pytest
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.sentry_provider.sentry_provider import SentryProvider


def _response(status_code: int, *, json_body=None, text: str = "") -> requests.Response:
    """Build a real requests.Response so .ok and .json() behave like the wire."""
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


def test_empty_error_body_does_not_abort_scope_validation(sentry_provider):
    """Sentry answers the deprecated /plugins/webhooks/ endpoint with a 404 and an empty
    text/html body. That must mark project:write as failed with the status, not raise and
    leave every other scope 'Not checked'."""
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


def test_json_detail_is_still_reported(sentry_provider):
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

    assert (
        scopes["project:write"] == "You do not have permission to perform this action."
    )
    assert scopes["event:read"] is True
    assert scopes["project:read"] is True


def test_json_body_without_detail_falls_back_to_the_status(sentry_provider):
    """A JSON error without 'detail' used to store None; the status is more useful."""
    with (
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.get",
            return_value=_response(401, json_body={"message": "bad token"}),
        ),
        patch(
            "keep.providers.sentry_provider.sentry_provider.requests.post",
            return_value=_response(401, json_body={}),
        ),
    ):
        scopes = sentry_provider.validate_scopes()

    assert scopes == {
        "event:read": "HTTP 401",
        "project:read": "HTTP 401",
        "project:write": "HTTP 401",
    }
