"""
Test for Lark Provider.
"""

import json
import pytest
from unittest.mock import Mock, patch

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.lark_provider.lark_provider import LarkProvider
from keep.providers.models.provider_config import ProviderConfig


@pytest.fixture
def lark_provider():
    """Fixture for Lark provider."""
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "app_id": "test_app_id",
            "app_secret": "test_secret"
        },
        name="test-lark"
    )
    
    provider = LarkProvider(context_manager, "lark", config)
    return provider


class TestLarkProvider:
    """Test class for LarkProvider."""

    def test_provider_config(self, lark_provider):
        """Test provider configuration validation."""
        assert lark_provider.authentication_config.app_id == "test_app_id"
        assert lark_provider.authentication_config.app_secret == "test_secret"

    @patch('requests.post')
    def test_get_access_token_success(self, mock_post, lark_provider):
        """Test successful access token retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        token = lark_provider._get_access_token()
        assert token == "test_token_123"

    @patch('requests.post')
    def test_get_access_token_failure(self, mock_post, lark_provider):
        """Test failed access token retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 1,
            "msg": "Invalid app credentials"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            lark_provider._get_access_token()
        assert "Failed to get access token" in str(exc_info.value)

    def test_format_alert_basic_ticket(self, lark_provider):
        """Test formatting a basic ticket event."""
        event = {
            "ticket_id": "TICKET-123",
            "title": "Database Connection Issue",
            "description": "Cannot connect to primary database",
            "priority": "high",
            "status": "open",
            "category": "Infrastructure",
            "assignee": "admin@company.com",
            "event_type": "ticket_created"
        }

        alert = lark_provider._format_alert(event)
        
        assert isinstance(alert, AlertDto)
        assert alert.id == "lark-TICKET-123-ticket_created"
        assert alert.name == "Database Connection Issue"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == "firing"
        assert alert.labels["provider"] == "lark"
        assert alert.labels["ticket_id"] == "TICKET-123"
        assert alert.labels["category"] == "Infrastructure"

    def test_format_alert_chinese_priority(self, lark_provider):
        """Test formatting alert with Chinese priority levels."""
        event = {
            "ticket_id": "TICKET-456",
            "title": "网络故障",
            "priority": "紧急",
            "status": "in_progress",
            "event_type": "ticket_update"
        }

        alert = lark_provider._format_alert(event)
        
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == "firing"

    def test_format_alert_resolved_status(self, lark_provider):
        """Test formatting alert with resolved status."""
        event = {
            "ticket_id": "TICKET-789",
            "title": "Issue Resolved",
            "priority": "medium",
            "status": "resolved",
            "event_type": "ticket_resolved"
        }

        alert = lark_provider._format_alert(event)
        
        assert alert.status == "resolved"
        assert alert.severity == AlertSeverity.MEDIUM

    def test_format_alert_minimal_data(self, lark_provider):
        """Test formatting alert with minimal event data."""
        event = {
            "ticket_id": "TICKET-MIN"
        }

        alert = lark_provider._format_alert(event)
        
        assert alert.id == "lark-TICKET-MIN-ticket_update"
        assert alert.name == "Lark Service Desk Notification"
        assert alert.severity == AlertSeverity.MEDIUM
        assert alert.status == "firing"

    def test_format_alert_numeric_priority(self, lark_provider):
        """Test formatting alert with numeric priority."""
        event = {
            "ticket_id": "TICKET-NUM",
            "title": "Numeric Priority Test",
            "priority": "4",
            "status": "pending",
            "event_type": "ticket_escalated"
        }

        alert = lark_provider._format_alert(event)
        
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == "pending"

    def test_format_alert_static_method(self):
        """Test the static format_alert method."""
        event = {
            "ticket_id": "STATIC-123",
            "title": "Static Method Test",
            "priority": "low",
            "status": "closed",
            "event_type": "ticket_closed"
        }

        alert = LarkProvider.format_alert(event)
        
        assert isinstance(alert, AlertDto)
        assert alert.id == "lark-STATIC-123-ticket_closed"
        assert alert.severity == AlertSeverity.LOW
        assert alert.status == "resolved"

    def test_severity_mapping_edge_cases(self, lark_provider):
        """Test severity mapping with various edge cases."""
        test_cases = [
            ("urgent", AlertSeverity.CRITICAL),
            ("CRITICAL", AlertSeverity.CRITICAL),
            ("Unknown", AlertSeverity.MEDIUM),  # Default fallback
            ("", AlertSeverity.MEDIUM),         # Empty string
            ("3", AlertSeverity.HIGH),          # Numeric string
        ]

        for priority, expected_severity in test_cases:
            event = {
                "ticket_id": "TEST",
                "priority": priority,
                "event_type": "test"
            }
            
            alert = lark_provider._format_alert(event)
            assert alert.severity == expected_severity, f"Failed for priority: {priority}"

    @patch('requests.post')
    def test_validate_scopes_success(self, mock_post, lark_provider):
        """Test successful scope validation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "valid_token"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        scopes = lark_provider.validate_scopes()
        assert scopes["webhook"] is True

    @patch('requests.post')
    def test_validate_scopes_failure(self, mock_post, lark_provider):
        """Test failed scope validation."""
        mock_post.side_effect = Exception("Network error")

        scopes = lark_provider.validate_scopes()
        assert scopes["webhook"] is False