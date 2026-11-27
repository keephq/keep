import logging
from unittest.mock import MagicMock, patch
import pytest
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.sentry_provider.sentry_provider import SentryProvider


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def sentry_config():
    return ProviderConfig(
        description="Test Sentry Provider",
        authentication={
            "api_key": "test_sentry_token",
            "organization_slug": "test_org",
            "api_url": "https://sentry.io/api/0",
            "project_slug": "frontend-app",
        },
    )


@pytest.fixture
def sentry_provider(context_manager, sentry_config):
    provider = SentryProvider(
        context_manager=context_manager,
        provider_id="sentry-test",
        config=sentry_config,
    )
    provider.validate_config()
    return provider


def test_paginate_single_page(sentry_provider):
    """Single page with no next link returns all items without extra requests."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"id": "ev_1"}, {"id": "ev_2"}]
    mock_resp.links = {}

    with patch("requests.get", return_value=mock_resp) as mock_get:
        results = sentry_provider._paginate("https://sentry.io/api/0/projects/test_org/p1/events/")
        assert len(results) == 2
        assert results[0]["id"] == "ev_1"
        assert results[1]["id"] == "ev_2"
        mock_get.assert_called_once()


def test_paginate_multi_page(sentry_provider):
    """Multiple pages are traversed following Link rel=next when results=true."""
    resp_page1 = MagicMock()
    resp_page1.ok = True
    resp_page1.json.return_value = [{"id": "ev_1"}, {"id": "ev_2"}]
    resp_page1.links = {
        "next": {
            "url": "https://sentry.io/api/0/projects/test_org/p1/events/?cursor=100:100:0",
            "rel": "next",
            "results": "true",
        }
    }

    resp_page2 = MagicMock()
    resp_page2.ok = True
    resp_page2.json.return_value = [{"id": "ev_3"}]
    resp_page2.links = {
        "next": {
            "url": "https://sentry.io/api/0/projects/test_org/p1/events/?cursor=100:200:0",
            "rel": "next",
            "results": "false",
        }
    }

    with patch("requests.get", side_effect=[resp_page1, resp_page2]) as mock_get:
        results = sentry_provider._paginate("https://sentry.io/api/0/projects/test_org/p1/events/")
        assert len(results) == 3
        assert [r["id"] for r in results] == ["ev_1", "ev_2", "ev_3"]
        assert mock_get.call_count == 2


def test_paginate_page_cap_warning(sentry_provider, caplog):
    """Pagination stops when page_cap is reached and logs a warning."""
    resp_continuous = MagicMock()
    resp_continuous.ok = True
    resp_continuous.json.return_value = [{"id": "ev_item"}]
    resp_continuous.links = {
        "next": {
            "url": "https://sentry.io/api/0/projects/test_org/p1/events/?cursor=next",
            "rel": "next",
            "results": "true",
        }
    }

    with caplog.at_level(logging.WARNING):
        with patch("requests.get", return_value=resp_continuous) as mock_get:
            results = sentry_provider._paginate(
                "https://sentry.io/api/0/projects/test_org/p1/events/", page_cap=3
            )
            assert len(results) == 3
            assert mock_get.call_count == 3
            assert any("Hit Sentry pagination cap (3 pages)" in record.message for record in caplog.records)


def test_get_issues_paginated(sentry_provider):
    """__get_issues collects all issues across pages and returns {id: issue} dict."""
    resp_p1 = MagicMock()
    resp_p1.ok = True
    resp_p1.json.return_value = [{"id": "issue_101", "status": "unresolved"}]
    resp_p1.links = {
        "next": {
            "url": "https://sentry.io/api/0/projects/test_org/p1/issues/?cursor=1",
            "rel": "next",
            "results": "true",
        }
    }

    resp_p2 = MagicMock()
    resp_p2.ok = True
    resp_p2.json.return_value = [{"id": "issue_102", "status": "resolved"}]
    resp_p2.links = {
        "next": {"results": "false"}
    }

    with patch("requests.get", side_effect=[resp_p1, resp_p2]):
        issues_dict = sentry_provider._SentryProvider__get_issues("frontend-app")
        assert len(issues_dict) == 2
        assert "issue_101" in issues_dict
        assert "issue_102" in issues_dict
        assert issues_dict["issue_101"]["status"] == "unresolved"
        assert issues_dict["issue_102"]["status"] == "resolved"


def test_get_alerts_pagination_integration(sentry_provider):
    """_get_alerts retrieves paginated events and issues and maps them to AlertDto."""
    events_p1 = MagicMock()
    events_p1.ok = True
    events_p1.json.return_value = [
        {
            "id": "event_1",
            "groupID": "issue_1",
            "title": "TypeError: Cannot read property of undefined",
            "culprit": "app.js in render",
            "dateCreated": "2026-11-10T12:00:00Z",
            "tags": [{"key": "level", "value": "error"}, {"key": "environment", "value": "production"}],
        }
    ]
    events_p1.links = {
        "next": {
            "url": "https://sentry.io/api/0/projects/test_org/frontend-app/events/?cursor=1",
            "rel": "next",
            "results": "true",
        }
    }

    events_p2 = MagicMock()
    events_p2.ok = True
    events_p2.json.return_value = [
        {
            "id": "event_2",
            "groupID": "issue_2",
            "title": "TimeoutError: Database connection timeout",
            "culprit": "db.js in query",
            "dateCreated": "2026-11-10T12:05:00Z",
            "tags": [{"key": "level", "value": "fatal"}, {"key": "environment", "value": "production"}],
        }
    ]
    events_p2.links = {"next": {"results": "false"}}

    issues_resp = MagicMock()
    issues_resp.ok = True
    issues_resp.json.return_value = [
        {"id": "issue_1", "status": "unresolved"},
        {"id": "issue_2", "status": "unresolved"},
    ]
    issues_resp.links = {"next": {"results": "false"}}

    with patch("requests.get", side_effect=[events_p1, events_p2, issues_resp]):
        alerts = sentry_provider._get_alerts()
        assert len(alerts) == 2
        assert isinstance(alerts[0], AlertDto)
        assert alerts[0].id == "event_1"
        assert alerts[0].name == "TypeError: Cannot read property of undefined"
        assert alerts[0].severity == AlertSeverity.HIGH.value or alerts[0].severity == AlertSeverity.HIGH
        assert alerts[0].status == AlertStatus.FIRING.value or alerts[0].status == AlertStatus.FIRING

        assert alerts[1].id == "event_2"
        assert alerts[1].name == "TimeoutError: Database connection timeout"
        assert alerts[1].severity == AlertSeverity.CRITICAL.value or alerts[1].severity == AlertSeverity.CRITICAL
