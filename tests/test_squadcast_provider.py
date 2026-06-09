"""Tests for Squadcast Provider."""

import json
import pytest
from unittest.mock import MagicMock, patch

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.squadcast_provider.squadcast_provider import (
    SquadcastProvider,
    SquadcastProviderAuthConfig,
)


@pytest.fixture
def context_manager():
    cm = MagicMock(spec=ContextManager)
    cm.tenant_id = "test-tenant"
    cm.workflow_id = "test-workflow"
    return cm


@pytest.fixture
def provider_config():
    return ProviderConfig(
        description="Test Squadcast",
        authentication={
            "api_key": "test-refresh-token",
            "webhook_url": "https://api.squadcast.com/v2/incidents/api/test-webhook",
            "api_url": "https://api.squadcast.com",
        },
    )


@pytest.fixture
def provider_config_api_only():
    return ProviderConfig(
        description="Test Squadcast API",
        authentication={
            "api_key": "test-refresh-token",
            "api_url": "https://api.squadcast.com",
        },
    )


@pytest.fixture
def provider(context_manager, provider_config):
    return SquadcastProvider(context_manager, "test-provider", provider_config)


@pytest.fixture
def provider_api_only(context_manager, provider_config_api_only):
    return SquadcastProvider(context_manager, "test-provider-api", provider_config_api_only)


class TestSquadcastProviderConfig:
    def test_validate_config(self, provider):
        """Test that config validation passes with correct config."""
        assert provider.authentication_config.api_key == "test-refresh-token"
        assert provider.authentication_config.webhook_url == (
            "https://api.squadcast.com/v2/incidents/api/test-webhook"
        )
        assert provider.authentication_config.api_url == "https://api.squadcast.com"

    def test_validate_config_minimal(self, context_manager):
        """Test that config validation passes with minimal config."""
        config = ProviderConfig(
            description="Minimal",
            authentication={"api_key": "my-token"},
        )
        p = SquadcastProvider(context_manager, "test", config)
        assert p.authentication_config.api_key == "my-token"
        assert p.authentication_config.webhook_url == ""
        assert p.authentication_config.api_url == "https://api.squadcast.com"

    def test_validate_config_missing_api_key(self, context_manager):
        """Test that config validation fails without api_key."""
        config = ProviderConfig(
            description="Missing key",
            authentication={},
        )
        with pytest.raises(TypeError):
            SquadcastProvider(context_manager, "test", config)


class TestSquadcastProviderAuth:
    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_get_access_token_success(self, mock_get, provider):
        """Test successful access token retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"access_token": "test-access-token"}
        }
        mock_get.return_value = mock_response

        token = provider._get_access_token()
        assert token == "test-access-token"
        mock_get.assert_called_once_with(
            "https://api.squadcast.com/v3/oauth/access-token",
            headers={"X-Refresh-Token": "test-refresh-token"},
            timeout=10,
        )

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_get_access_token_failure(self, mock_get, provider):
        """Test failed access token retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="Failed to obtain Squadcast access token"):
            provider._get_access_token()

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_validate_scopes_success(self, mock_get, provider):
        """Test successful scope validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"access_token": "test-access-token"}
        }
        mock_get.return_value = mock_response

        scopes = provider.validate_scopes()
        assert scopes == {"authenticated": True}

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_validate_scopes_failure(self, mock_get, provider):
        """Test failed scope validation."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_get.return_value = mock_response

        scopes = provider.validate_scopes()
        assert "authenticated" in scopes
        assert scopes["authenticated"] != True


class TestSquadcastProviderNotify:
    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.post")
    def test_notify_via_webhook(self, mock_post, provider):
        """Test notify via webhook URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.text = '{"status": "ok"}'
        mock_post.return_value = mock_response

        result = provider._notify(
            message="Test alert",
            description="Test description",
            priority="P2",
            status="trigger",
            event_id="evt-123",
        )

        assert result == {"status": "ok"}
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == (
            "https://api.squadcast.com/v2/incidents/api/test-webhook"
        )
        payload = call_kwargs[1]["json"]
        assert payload["message"] == "Test alert"
        assert payload["description"] == "Test description"
        assert payload["priority"] == "P2"
        assert payload["event_id"] == "evt-123"

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.post")
    def test_notify_via_webhook_with_tags(self, mock_post, provider):
        """Test notify via webhook with tags."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "inc-123"}
        mock_response.text = '{"id": "inc-123"}'
        mock_post.return_value = mock_response

        tags = {"environment": "production", "region": "us-east-1"}
        result = provider._notify(
            message="Tagged alert",
            tags=tags,
        )

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["tags"] == tags

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.post")
    def test_notify_via_webhook_failure(self, mock_post, provider):
        """Test notify via webhook failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with pytest.raises(Exception, match="Failed to create Squadcast incident via webhook"):
            provider._notify(message="Failing alert")

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.post")
    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_notify_via_api(self, mock_get, mock_post, provider_api_only):
        """Test notify via REST API."""
        # Mock access token
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "data": {"access_token": "access-123"}
        }
        mock_get.return_value = mock_get_response

        # Mock incident creation
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"data": {"id": "inc-456"}}
        mock_post.return_value = mock_post_response

        result = provider_api_only._notify(
            message="API alert",
            description="Created via API",
            service_id="svc-001",
            escalation_policy_id="ep-001",
            priority="P1",
        )

        assert result == {"data": {"id": "inc-456"}}
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["message"] == "API alert"
        assert payload["service_id"] == "svc-001"
        assert payload["escalation_policy_id"] == "ep-001"

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_notify_via_api_missing_service_id(self, mock_get, provider_api_only):
        """Test notify via API fails without service_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"access_token": "access-123"}
        }
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="service_id is required"):
            provider_api_only._notify(message="No service")


class TestSquadcastProviderQuery:
    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_query_incidents(self, mock_get, provider):
        """Test querying incidents."""
        mock_responses = [
            # First call: access token
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"data": {"access_token": "tok"}}),
            ),
            # Second call: incidents
            MagicMock(
                status_code=200,
                json=MagicMock(
                    return_value={
                        "data": [
                            {"id": "inc-1", "message": "Alert 1"},
                            {"id": "inc-2", "message": "Alert 2"},
                        ]
                    }
                ),
            ),
        ]
        mock_get.side_effect = mock_responses

        result = provider._query(query_type="incidents")
        assert len(result) == 2
        assert result[0]["id"] == "inc-1"

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_query_services(self, mock_get, provider):
        """Test querying services."""
        mock_responses = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"data": {"access_token": "tok"}}),
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(
                    return_value={
                        "data": [{"id": "svc-1", "name": "Web Service"}]
                    }
                ),
            ),
        ]
        mock_get.side_effect = mock_responses

        result = provider._query(query_type="services")
        assert len(result) == 1
        assert result[0]["name"] == "Web Service"

    @patch("keep.providers.squadcast_provider.squadcast_provider.requests.get")
    def test_query_escalation_policies(self, mock_get, provider):
        """Test querying escalation policies."""
        mock_responses = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"data": {"access_token": "tok"}}),
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(
                    return_value={
                        "data": [{"id": "ep-1", "name": "Default"}]
                    }
                ),
            ),
        ]
        mock_get.side_effect = mock_responses

        result = provider._query(query_type="escalation_policies")
        assert len(result) == 1
        assert result[0]["name"] == "Default"

    def test_query_unknown_type(self, provider):
        """Test query with unknown type raises."""
        with pytest.raises(Exception, match="Unknown query type"):
            provider._query(query_type="unknown")


class TestSquadcastProviderFormatAlert:
    def test_format_alert_triggered(self):
        """Test formatting triggered incident."""
        event = {
            "id": "inc-123",
            "event_type": "incident_triggered",
            "message": "High CPU on prod",
            "description": "CPU > 95%",
            "priority": "P1",
            "service": {"id": "svc-1", "name": "Production"},
            "tags": [{"key": "env", "value": "prod"}],
            "created_at": "2023-10-01T12:00:00Z",
            "url": "https://app.squadcast.com/incident/inc-123",
        }

        alert = SquadcastProvider._format_alert(event)
        assert alert.id == "inc-123"
        assert alert.name == "High CPU on prod"
        assert alert.status == "firing"
        assert alert.severity == "critical"
        assert alert.description == "CPU > 95%"
        assert "squadcast" in alert.source
        assert alert.service == "Production"
        assert alert.tags == {"env": "prod"}

    def test_format_alert_resolved(self):
        """Test formatting resolved incident."""
        event = {
            "id": "inc-456",
            "event_type": "incident_resolved",
            "message": "Disk space low",
            "description": "",
            "priority": "P3",
            "service": {"id": "svc-2", "name": "Storage"},
            "tags": {},
            "created_at": "2023-10-01T14:00:00Z",
        }

        alert = SquadcastProvider._format_alert(event)
        assert alert.status == "resolved"
        assert alert.severity == "warning"

    def test_format_alert_acknowledged(self):
        """Test formatting acknowledged incident."""
        event = {
            "id": "inc-789",
            "event_type": "incident_acknowledged",
            "message": "Memory alert",
            "priority": "P2",
            "service": "My Service",
        }

        alert = SquadcastProvider._format_alert(event)
        assert alert.status == "acknowledged"
        assert alert.severity == "high"
        assert alert.service == "My Service"

    def test_format_alert_default_values(self):
        """Test formatting with missing fields."""
        event = {}
        alert = SquadcastProvider._format_alert(event)
        assert alert.name == "Squadcast Incident"
        assert alert.status == "firing"
        assert alert.severity == "info"

    def test_webhook_example(self):
        """Test that webhook example is valid and formattable."""
        example = SquadcastProvider.webhook_example()
        alert = SquadcastProvider._format_alert(example)
        assert alert.id == "60c6b0a4e4b0a2001c9a1234"
        assert alert.name == "High CPU usage on prod-web-01"
        assert alert.status == "firing"
        assert alert.severity == "high"
