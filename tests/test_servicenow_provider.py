"""Tests for ServiceNow Provider with Activity Sync.

Tests incident activity sync, work notes, comments, and status mapping.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime

from keep.api.models.incident import IncidentDto, IncidentStatus, IncidentSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.servicenow_provider.servicenow_provider import ServicenowProvider
from keep.providers.models.provider_config import ProviderConfig


class TestServicenowProvider:
    """Test suite for ServiceNow Provider."""

    @pytest.fixture
    def servicenow_config(self):
        return ProviderConfig(
            description="Test ServiceNow",
            authentication={
                "service_now_base_url": "https://test.service-now.com",
                "username": "admin",
                "password": "password",
            },
        )

    @pytest.fixture
    def servicenow_provider(self, servicenow_config):
        cm = ContextManager(tenant_id="test", workflow_id="test")
        return ServicenowProvider(cm, "test-servicenow", servicenow_config)

    @pytest.fixture
    def sample_incident(self):
        return {
            "sys_id": "abc123",
            "number": "INC001",
            "short_description": "Test Incident",
            "description": "Test description",
            "state": "1",  # New
            "impact": "1",  # Critical
            "opened_at": "2024-01-15 08:30:00",
            "assigned_to": {"display_value": "John Doe"},
        }

    @pytest.fixture
    def sample_journal_entries(self):
        return [
            {
                "sys_id": "journal1",
                "sys_created_on": "2024-01-15 09:00:00",
                "sys_created_by": "admin",
                "element": "work_notes",
                "value": "Investigating issue",
                "field_label": "Work notes",
            },
            {
                "sys_id": "journal2",
                "sys_created_on": "2024-01-15 10:00:00",
                "sys_created_by": "user1",
                "element": "comments",
                "value": "Thanks for update",
                "field_label": "Comments",
            },
        ]

    # Format Incident Tests
    def test_format_incident_new_state(self, sample_incident):
        """Test formatting NEW state incident."""
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.status == IncidentStatus.FIRING
        assert incident.severity == IncidentSeverity.CRITICAL

    def test_format_incident_in_progress(self, sample_incident):
        """Test formatting IN PROGRESS state."""
        sample_incident["state"] = "2"
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.status == IncidentStatus.FIRING

    def test_format_incident_on_hold(self, sample_incident):
        """Test formatting ON HOLD state."""
        sample_incident["state"] = "3"
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.status == IncidentStatus.ACKNOWLEDGED

    def test_format_incident_resolved(self, sample_incident):
        """Test formatting RESOLVED state."""
        sample_incident["state"] = "6"
        sample_incident["resolved_at"] = "2024-01-15 12:00:00"
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.status == IncidentStatus.RESOLVED

    def test_format_incident_closed(self, sample_incident):
        """Test formatting CLOSED state."""
        sample_incident["state"] = "7"
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.status == IncidentStatus.RESOLVED

    def test_format_incident_severity_mapping(self):
        """Test all severity mappings."""
        test_cases = [
            ("1", IncidentSeverity.CRITICAL),
            ("2", IncidentSeverity.HIGH),
            ("3", IncidentSeverity.WARNING),
            ("4", IncidentSeverity.INFO),
        ]
        for impact, expected in test_cases:
            data = {
                "sys_id": "test",
                "number": "INC001",
                "short_description": "Test",
                "state": "1",
                "impact": impact,
                "opened_at": "2024-01-01 00:00:00",
            }
            incident = ServicenowProvider._format_incident(data)
            assert incident.severity == expected

    def test_format_incident_with_assignee(self, sample_incident):
        """Test assignee extraction."""
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.assignee == "John Doe"

    def test_format_incident_no_description(self, sample_incident):
        """Test using short_description when description empty."""
        sample_incident["description"] = ""
        incident = ServicenowProvider._format_incident(sample_incident)
        assert incident.user_summary == "Test Incident"

    # Activity Tests
    @patch("requests.get")
    def test_get_incident_activities_success(self, mock_get, servicenow_provider, sample_journal_entries):
        """Test fetching activities successfully."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"result": sample_journal_entries}
        mock_get.return_value = mock_response

        activities = servicenow_provider._get_incident_activities("abc123")
        assert len(activities) == 2
        assert activities[0]["type"] == "Work notes"
        assert activities[1]["type"] == "Comments"

    @patch("requests.get")
    def test_get_incident_activities_empty(self, mock_get, servicenow_provider):
        """Test fetching activities with empty result."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        activities = servicenow_provider._get_incident_activities("abc123")
        assert activities == []

    @patch("requests.get")
    def test_get_incident_activities_error(self, mock_get, servicenow_provider):
        """Test handling API error when fetching activities."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        activities = servicenow_provider._get_incident_activities("abc123")
        assert activities == []

    @patch("requests.patch")
    def test_add_incident_activity_work_notes(self, mock_patch, servicenow_provider):
        """Test adding work notes."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_patch.return_value = mock_response

        servicenow_provider._add_incident_activity("abc123", "Test note", "work_notes")
        mock_patch.assert_called_once()

    @patch("requests.patch")
    def test_add_incident_activity_comments(self, mock_patch, servicenow_provider):
        """Test adding comments."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_patch.return_value = mock_response

        servicenow_provider._add_incident_activity("abc123", "Test comment", "comments")
        mock_patch.assert_called_once()

    # Sync Tests
    @patch.object(ServicenowProvider, "_get_incident_activities")
    @patch.object(ServicenowProvider, "_add_incident_activity")
    def test_sync_activities_bidirectional(self, mock_add, mock_get, servicenow_provider):
        """Test bidirectional sync."""
        mock_get.return_value = [{"id": "sn1", "content": "From SN"}]
        mock_add.return_value = {"sys_id": "abc123"}

        result = servicenow_provider.sync_incident_activities(
            "abc123",
            [{"content": "From Keep"}],
            sync_to_servicenow=True,
            sync_from_servicenow=True,
        )
        assert result["sync_status"] == "success"

    @patch.object(ServicenowProvider, "_get_incident_activities")
    @patch.object(ServicenowProvider, "_add_incident_activity")
    def test_sync_activities_pull_only(self, mock_add, mock_get, servicenow_provider):
        """Test pull-only sync."""
        mock_get.return_value = [{"id": "sn1"}]

        servicenow_provider.sync_incident_activities(
            "abc123",
            [{"content": "Should not sync"}],
            sync_to_servicenow=False,
            sync_from_servicenow=True,
        )
        mock_add.assert_not_called()
