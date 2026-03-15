"""
Test for Jira provider priority field handling.
"""

import json
import pytest
from unittest.mock import Mock, patch
import responses

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.jira_provider.jira_provider import JiraProvider
from keep.providers.models.provider_config import ProviderConfig


@pytest.fixture
def jira_provider():
    """Fixture for Jira provider."""
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "email": "test@test.com",
            "api_token": "test_token",
            "host": "https://test.atlassian.net"
        },
        name="test-jira"
    )
    
    provider = JiraProvider(context_manager, "jira", config)
    return provider


class TestJiraPriorityHandling:
    """Test class for Jira priority field handling."""

    @responses.activate
    def test_create_issue_excludes_none_priority(self, jira_provider):
        """Test that priority with 'none' value is excluded from request."""
        
        # Mock the create issue endpoint
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/2/issue",
            json={"id": "123", "key": "TEST-123", "self": "https://test.atlassian.net/rest/api/2/issue/123"},
            status=201
        )

        # Call the create issue method with priority: "none"
        result = jira_provider._JiraProvider__create_issue(
            project_key="TEST",
            summary="Test Issue", 
            description="Test Description",
            issue_type="Bug",
            custom_fields={"priority": "none"}
        )

        # Verify the request was made without priority field
        assert len(responses.calls) == 1
        request_body = json.loads(responses.calls[0].request.body)
        
        # Priority should not be in the fields
        assert "priority" not in request_body["fields"]
        assert "summary" in request_body["fields"]
        assert request_body["fields"]["summary"] == "Test Issue"

    @responses.activate 
    def test_create_issue_excludes_empty_priority(self, jira_provider):
        """Test that priority with empty value is excluded from request."""
        
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/2/issue", 
            json={"id": "124", "key": "TEST-124", "self": "https://test.atlassian.net/rest/api/2/issue/124"},
            status=201
        )

        # Test with empty string priority
        jira_provider._JiraProvider__create_issue(
            project_key="TEST",
            summary="Test Issue",
            description="Test Description", 
            issue_type="Bug",
            custom_fields={"priority": ""}
        )

        request_body = json.loads(responses.calls[0].request.body)
        assert "priority" not in request_body["fields"]

    @responses.activate
    def test_create_issue_excludes_null_priority(self, jira_provider):
        """Test that priority with null value is excluded from request."""
        
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/2/issue",
            json={"id": "125", "key": "TEST-125", "self": "https://test.atlassian.net/rest/api/2/issue/125"},
            status=201
        )

        # Test with None priority
        jira_provider._JiraProvider__create_issue(
            project_key="TEST", 
            summary="Test Issue",
            description="Test Description",
            issue_type="Bug",
            custom_fields={"priority": None}
        )

        request_body = json.loads(responses.calls[0].request.body)
        assert "priority" not in request_body["fields"]

    @responses.activate
    def test_create_issue_includes_valid_priority(self, jira_provider):
        """Test that valid priority values are included in request."""
        
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/2/issue",
            json={"id": "126", "key": "TEST-126", "self": "https://test.atlassian.net/rest/api/2/issue/126"},
            status=201
        )

        # Test with valid priority
        jira_provider._JiraProvider__create_issue(
            project_key="TEST",
            summary="Test Issue", 
            description="Test Description",
            issue_type="Bug",
            custom_fields={"priority": {"name": "High"}}
        )

        request_body = json.loads(responses.calls[0].request.body)
        assert "priority" in request_body["fields"]
        assert request_body["fields"]["priority"] == {"name": "High"}

    @responses.activate
    def test_create_issue_preserves_other_custom_fields(self, jira_provider):
        """Test that other custom fields are preserved when priority is filtered."""
        
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/2/issue",
            json={"id": "127", "key": "TEST-127", "self": "https://test.atlassian.net/rest/api/2/issue/127"},
            status=201
        )

        # Test with priority: none and other custom fields
        jira_provider._JiraProvider__create_issue(
            project_key="TEST",
            summary="Test Issue",
            description="Test Description",
            issue_type="Bug", 
            custom_fields={
                "priority": "none",
                "customfield_12345": "Custom Value",
                "environment": "Production"
            }
        )

        request_body = json.loads(responses.calls[0].request.body)
        
        # Priority should be filtered out
        assert "priority" not in request_body["fields"]
        
        # Other custom fields should be preserved
        assert "customfield_12345" in request_body["fields"]
        assert "environment" in request_body["fields"]
        assert request_body["fields"]["customfield_12345"] == "Custom Value"
        assert request_body["fields"]["environment"] == "Production"