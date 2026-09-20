import pytest
import requests

from tests.fixtures.client import test_app  # noqa


@pytest.fixture(autouse=True)
def discovery_network_requests(monkeypatch):
    requests_made = []
    monkeypatch.setenv("AUTH0_DOMAIN", "test-domain.auth0.com")

    def reject_network(self, method, url, **kwargs):
        requests_made.append(url)
        raise AssertionError("App fixture must not perform real HTTP requests")

    monkeypatch.setattr(requests.Session, "request", reject_network)
    return requests_made


@pytest.mark.parametrize(
    "test_app",
    [
        "AUTH0",
        "MULTI_TENANT",
        {"AUTH_TYPE": "AUTH0", "AUTH0_DOMAIN": "test-domain.auth0.com"},
        {"AUTH_TYPE": "MULTI_TENANT", "AUTH0_DOMAIN": "test-domain.auth0.com"},
    ],
    indirect=True,
)
def test_auth0_app_fixture_does_not_contact_discovery_endpoint(
    test_app, discovery_network_requests
):
    assert test_app is not None
    # Discovery catches network errors and falls back, so inspect attempted calls
    # as well as rejecting them to detect a missing mock.
    assert discovery_network_requests == []
