"""Tests for ServiceNow provider incident sync functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.incident import IncidentDto, IncidentStatus, IncidentSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.servicenow_provider.servicenow_provider import (
    ServicenowProvider,
)


@pytest.fixture
def servicenow_provider():
    """Create a ServiceNow provider instance for testing."""
    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"

    config = ProviderConfig(
        description="Test ServiceNow Provider",
        authentication={
            "service_now_base_url": "https://test.service-now.com",
            "username": "admin",
            "password": "admin",
        },
    )

    provider = ServicenowProvider(
        context_manager=context_manager,
        provider_id="servicenow-test",
        config=config,
    )
    return provider


class TestFormatIncident:
    """Tests for _format_incident static method."""

    def test_basic_incident_formatting(self):
        """Test formatting a standard ServiceNow incident."""
        event = {
            "incident": {
                "number": "INC0010001",
                "short_description": "Server is down",
                "description": "The production server is not responding.",
                "state": "1",
                "impact": "1",
                "sys_created_on": "2025-01-15 10:30:00",
                "assigned_to": {"display_value": "John Doe", "value": "abc123"},
                "assignment_group": {"display_value": "IT Operations", "value": "grp1"},
                "category": "Hardware",
            }
        }

        result = ServicenowProvider._format_incident(event)

        assert isinstance(result, IncidentDto)
        assert result.fingerprint == "INC0010001"
        assert result.status == IncidentStatus.FIRING
        assert result.severity == IncidentSeverity.CRITICAL
        assert "Server is down" in result.user_generated_name
        assert result.assignee == "John Doe"
        assert "IT Operations" in result.services

    def test_resolved_incident(self):
        """Test formatting a resolved incident."""
        event = {
            "incident": {
                "number": "INC0010002",
                "short_description": "Resolved issue",
                "state": "6",
                "impact": "3",
                "sys_created_on": "2025-01-10 08:00:00",
                "resolved_at": "2025-01-10 12:00:00",
            }
        }

        result = ServicenowProvider._format_incident(event)

        assert result.status == IncidentStatus.RESOLVED
        assert result.severity == IncidentSeverity.LOW
        assert result.end_time is not None

    def test_acknowledged_incident(self):
        """Test formatting an in-progress incident (state 2)."""
        event = {
            "incident": {
                "number": "INC0010003",
                "short_description": "In progress",
                "state": "2",
                "impact": "2",
                "sys_created_on": "2025-01-12 09:00:00",
            }
        }

        result = ServicenowProvider._format_incident(event)
        assert result.status == IncidentStatus.ACKNOWLEDGED
        assert result.severity == IncidentSeverity.WARNING

    def test_missing_number_returns_empty(self):
        """Test that an incident without a number returns empty list."""
        event = {"incident": {"short_description": "No number"}}
        result = ServicenowProvider._format_incident(event)
        assert result == []

    def test_deterministic_id(self):
        """Test that the same incident number always produces the same UUID."""
        id1 = ServicenowProvider._get_incident_id("INC0010001")
        id2 = ServicenowProvider._get_incident_id("INC0010001")
        assert id1 == id2

        id3 = ServicenowProvider._get_incident_id("INC0010002")
        assert id1 != id3


class TestGetIncidents:
    """Tests for _get_incidents method."""

    def test_get_incidents_success(self, servicenow_provider):
        """Test successful incident pulling."""
        mock_incidents = [
            {
                "number": "INC0010001",
                "short_description": "Test incident 1",
                "state": "1",
                "impact": "1",
                "sys_created_on": "2025-01-15 10:30:00",
                "sys_id": "abc123",
            },
            {
                "number": "INC0010002",
                "short_description": "Test incident 2",
                "state": "6",
                "impact": "3",
                "sys_created_on": "2025-01-14 08:00:00",
                "sys_id": "def456",
            },
        ]

        with patch.object(
            servicenow_provider, "_query", return_value=mock_incidents
        ):
            incidents = servicenow_provider._get_incidents()

        assert len(incidents) == 2
        assert incidents[0].fingerprint == "INC0010001"
        assert incidents[1].fingerprint == "INC0010002"

    def test_get_incidents_empty(self, servicenow_provider):
        """Test pulling when no incidents exist."""
        with patch.object(servicenow_provider, "_query", return_value=[]):
            incidents = servicenow_provider._get_incidents()

        assert incidents == []


class TestGetIncidentActivities:
    """Tests for get_incident_activities method."""

    def test_get_activities_by_number(self, servicenow_provider):
        """Test fetching activities using incident number."""
        # Mock the sys_id resolution
        resolve_response = MagicMock()
        resolve_response.ok = True
        resolve_response.json.return_value = {
            "result": [{"sys_id": "abc123def456"}]
        }

        # Mock the journal query
        journal_response = MagicMock()
        journal_response.ok = True
        journal_response.json.return_value = {
            "result": [
                {
                    "sys_id": "journal1",
                    "element": "work_notes",
                    "value": "Investigating the issue",
                    "sys_created_on": "2025-01-15 11:00:00",
                    "sys_created_by": "admin",
                },
                {
                    "sys_id": "journal2",
                    "element": "comments",
                    "value": "Customer notified",
                    "sys_created_on": "2025-01-15 11:30:00",
                    "sys_created_by": "admin",
                },
            ]
        }

        with patch("requests.get", side_effect=[resolve_response, journal_response]):
            activities = servicenow_provider.get_incident_activities("INC0010001")

        assert len(activities) == 2
        assert activities[0]["type"] == "work_notes"
        assert activities[0]["content"] == "Investigating the issue"
        assert activities[1]["type"] == "comments"

    def test_get_activities_not_found(self, servicenow_provider):
        """Test fetching activities for non-existent incident."""
        resolve_response = MagicMock()
        resolve_response.ok = True
        resolve_response.json.return_value = {"result": []}

        with patch("requests.get", return_value=resolve_response):
            activities = servicenow_provider.get_incident_activities("INC9999999")

        assert activities == []


class TestAddIncidentActivity:
    """Tests for add_incident_activity method."""

    def test_add_work_note(self, servicenow_provider):
        """Test adding a work note to an incident."""
        resolve_response = MagicMock()
        resolve_response.ok = True
        resolve_response.json.return_value = {
            "result": [{"sys_id": "abc123"}]
        }

        patch_response = MagicMock()
        patch_response.ok = True
        patch_response.json.return_value = {
            "result": {"sys_id": "abc123", "work_notes": "Test note"}
        }

        with patch("requests.get", return_value=resolve_response), patch(
            "requests.patch", return_value=patch_response
        ):
            result = servicenow_provider.add_incident_activity(
                incident_id="INC0010001",
                content="Test work note",
                activity_type="work_notes",
            )

        assert result["sys_id"] == "abc123"

    def test_add_comment(self, servicenow_provider):
        """Test adding a comment to an incident."""
        resolve_response = MagicMock()
        resolve_response.ok = True
        resolve_response.json.return_value = {
            "result": [{"sys_id": "abc123"}]
        }

        patch_response = MagicMock()
        patch_response.ok = True
        patch_response.json.return_value = {
            "result": {"sys_id": "abc123", "comments": "Customer update"}
        }

        with patch("requests.get", return_value=resolve_response), patch(
            "requests.patch", return_value=patch_response
        ):
            result = servicenow_provider.add_incident_activity(
                incident_id="INC0010001",
                content="Customer update",
                activity_type="comments",
            )

        assert result["sys_id"] == "abc123"

    def test_invalid_activity_type(self, servicenow_provider):
        """Test that invalid activity type raises exception."""
        from keep.exceptions.provider_exception import ProviderException

        with pytest.raises(ProviderException, match="Invalid activity_type"):
            servicenow_provider.add_incident_activity(
                incident_id="INC0010001",
                content="test",
                activity_type="invalid",
            )


class TestResolveSysId:
    """Tests for _resolve_incident_sys_id method."""

    def test_resolve_sys_id_passthrough(self, servicenow_provider):
        """Test that a 32-char hex string is returned as-is."""
        sys_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        result = servicenow_provider._resolve_incident_sys_id(sys_id)
        assert result == sys_id

    def test_resolve_incident_number(self, servicenow_provider):
        """Test resolving an incident number to sys_id."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "result": [{"sys_id": "resolved_sys_id"}]
        }

        with patch("requests.get", return_value=mock_response):
            result = servicenow_provider._resolve_incident_sys_id("INC0010001")

        assert result == "resolved_sys_id"

    def test_resolve_empty_returns_none(self, servicenow_provider):
        """Test that empty input returns None."""
        result = servicenow_provider._resolve_incident_sys_id("")
        assert result is None

        result = servicenow_provider._resolve_incident_sys_id(None)
        assert result is None


class TestProviderConfig:
    """Tests for provider configuration."""

    def test_provider_category(self):
        """Test that Incident Management is in the category list."""
        assert "Incident Management" in ServicenowProvider.PROVIDER_CATEGORY
        assert "Ticketing" in ServicenowProvider.PROVIDER_CATEGORY

    def test_provider_methods(self):
        """Test that PROVIDER_METHODS are properly defined."""
        method_names = [m.name for m in ServicenowProvider.PROVIDER_METHODS]
        assert "Get Incidents" in method_names
        assert "Get Incident Activities" in method_names
        assert "Add Incident Activity" in method_names

    def test_status_mapping_coverage(self):
        """Test that all common ServiceNow states are mapped."""
        # New, In Progress, On Hold, Resolved, Closed, Canceled
        for state in ["1", "2", "3", "6", "7", "8"]:
            assert state in ServicenowProvider.INCIDENT_STATUS_MAP

    def test_severity_mapping_coverage(self):
        """Test that all ServiceNow impact levels are mapped."""
        for impact in ["1", "2", "3"]:
            assert impact in ServicenowProvider.INCIDENT_SEVERITY_MAP
