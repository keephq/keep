"""Tests for BMC Helix ITSM Provider."""

import json
import pytest
from unittest.mock import MagicMock, patch

from keep.providers.bmc_itsm_provider.bmc_itsm_provider import (
    BmcItsmProvider,
    BmcItsmProviderAuthConfig,
    BMC_SEVERITY_MAP,
    BMC_STATUS_MAP,
)
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig


@pytest.fixture
def provider():
    """Create a BmcItsmProvider instance for testing."""
    return BmcItsmProvider(
        context_manager=ContextManager(context_id="test"),
        provider_id="bmc-itsm-test",
        config=ProviderConfig(
            authentication={
                "bmc_base_url": "https://test.onbmc.com",
                "username": "testuser",
                "password": "testpass",
            }
        ),
    )


@pytest.fixture
def provider_with_token():
    """Create a BmcItsmProvider instance with token auth."""
    return BmcItsmProvider(
        context_manager=ContextManager(context_id="test"),
        provider_id="bmc-itsm-token-test",
        config=ProviderConfig(
            authentication={
                "bmc_base_url": "https://test.onbmc.com",
                "auth_token": "test-token-123",
            }
        ),
    )


class TestBmcItsmProviderAuth:
    """Test authentication configuration."""

    def test_basic_auth(self, provider):
        """Test basic auth is set up correctly."""
        auth = provider._get_auth()
        assert auth.username == "testuser"
        assert auth.password == "testpass"

    def test_token_auth(self, provider_with_token):
        """Test token auth returns None for basic auth."""
        auth = provider_with_token._get_auth()
        assert auth is None

    def test_headers_with_basic_auth(self, provider):
        """Test headers with basic auth."""
        headers = provider._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_token_auth(self, provider_with_token):
        """Test headers include Bearer token."""
        headers = provider_with_token._get_headers()
        assert headers["Authorization"] == "Bearer test-token-123"

    def test_base_url_no_trailing_slash(self, provider):
        """Test base URL has no trailing slash."""
        assert provider._base_url == "https://test.onbmc.com"


class TestBmcItsmProviderValidation:
    """Test configuration validation."""

    def test_validate_config_success(self, provider):
        """Test valid config passes validation."""
        provider.validate_config()  # Should not raise

    def test_validate_config_with_token(self, provider_with_token):
        """Test valid config with token passes validation."""
        provider_with_token.validate_config()  # Should not raise

    def test_validate_config_missing_url(self):
        """Test missing URL raises exception."""
        p = BmcItsmProvider(
            context_manager=ContextManager(context_id="test"),
            provider_id="test",
            config=ProviderConfig(
                authentication={
                    "bmc_base_url": "",
                    "username": "test",
                    "password": "test",
                }
            ),
        )
        with pytest.raises(Exception):
            p.validate_config()


class TestBmcItsmProviderIncidents:
    """Test incident operations."""

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_get_incidents(self, mock_get, provider):
        """Test pulling incidents."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "values": [
                {
                    "id": "INC000001",
                    "summary": "Test Incident",
                    "description": "Test description",
                    "priority": "2-High",
                    "status": "Assigned",
                    "createDate": "2024-01-01T00:00:00Z",
                    "modifiedDate": "2024-01-01T01:00:00Z",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        incidents = provider._get_incidents()
        assert len(incidents) == 1
        assert incidents[0].id == "INC000001"
        assert incidents[0].name == "Test Incident"
        assert incidents[0].source == "bmc_itsm"

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_get_incidents_empty(self, mock_get, provider):
        """Test pulling incidents when none exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"values": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        incidents = provider._get_incidents()
        assert len(incidents) == 0

    def test_format_incident(self, provider):
        """Test incident formatting."""
        raw = {
            "id": "INC000002",
            "summary": "Server Down",
            "description": "Production server is down",
            "priority": "1-Critical",
            "status": "New",
            "createDate": "2024-01-01T00:00:00Z",
            "modifiedDate": "2024-01-01T01:00:00Z",
        }
        incident = provider._format_incident(raw)
        assert incident.id == "INC000002"
        assert incident.name == "Server Down"
        assert incident.severity.value == "critical"
        assert incident.status.value == "open"

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.post")
    def test_create_incident(self, mock_post, provider):
        """Test creating an incident."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "INC000003"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = provider.create_incident(
            summary="New Incident",
            description="Something broke",
            impact="2-High",
            urgency="2-High",
        )
        assert result["id"] == "INC000003"
        mock_post.assert_called_once()

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_get_incident_by_id(self, mock_get, provider):
        """Test getting a specific incident."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "INC000001", "summary": "Test"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.get_incident("INC000001")
        assert result["id"] == "INC000001"

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_search_incidents(self, mock_get, provider):
        """Test searching incidents."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "values": [{"id": "INC000001", "summary": "Found"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = provider.search_incidents("status=New")
        assert len(results) == 1


class TestBmcItsmProviderTopology:
    """Test topology operations."""

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_pull_topology(self, mock_get, provider):
        """Test pulling topology data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "values": [
                {"id": "CI001", "name": "Web Server", "type": "Server"},
                {"id": "CI002", "name": "Database", "type": "Database"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        services, edges = provider.pull_topology()
        assert len(services) == 2
        assert services[0].name == "Web Server"

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_pull_topology_404(self, mock_get, provider):
        """Test topology when CMDB API is not available."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")
        mock_get.return_value = mock_response

        services, edges = provider.pull_topology()
        assert len(services) == 0


class TestBmcItsmProviderAlerts:
    """Test alert formatting."""

    def test_format_alert(self, provider):
        """Test alert formatting from BMC event."""
        event = {
            "id": "EVT001",
            "summary": "High CPU",
            "priority": "Critical",
            "status": "New",
        }
        alert = provider._format_alert(event)
        assert alert.id == "EVT001"
        assert alert.name == "High CPU"
        assert alert.severity.value == "critical"
        assert alert.status.value == "firing"

    def test_extract_type(self):
        """Test alert type extraction."""
        result = BmcItsmProvider._extract_type({"type": "custom-type"})
        assert result == "custom-type"

        result = BmcItsmProvider._extract_type({})
        assert result == "bmc-itsm-alert"


class TestBmcItsmProviderHealth:
    """Test health check."""

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_health_healthy(self, mock_get, provider):
        """Test health check when API is reachable."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        health = provider.get_health()
        assert health["healthy"] is True

    @patch("keep.providers.bmc_itsm_provider.bmc_itsm_provider.requests.get")
    def test_health_unhealthy(self, mock_get, provider):
        """Test health check when API is unreachable."""
        mock_get.side_effect = Exception("Connection refused")

        health = provider.get_health()
        assert health["healthy"] is False
