from unittest.mock import patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.jira_provider.jira_provider import JiraProvider
from keep.providers.jiraonprem_provider.jiraonprem_provider import JiraonpremProvider
from keep.providers.models.provider_config import ProviderConfig


class TestJiraProvider:
    @pytest.fixture
    def context_manager(self):
        return ContextManager(tenant_id="test", workflow_id="test")

    @pytest.fixture
    def jira_config(self):
        return ProviderConfig(
            description="Test Jira Provider",
            authentication={
                "email": "test@example.com",
                "api_token": "test_token",
                "host": "https://test.atlassian.net",
            },
        )

    @pytest.fixture
    def jira_provider(self, context_manager, jira_config):
        return JiraProvider(context_manager, "test_jira", jira_config)

    @pytest.fixture
    def jiraonprem_config(self):
        return ProviderConfig(
            description="Test Jira On-Prem Provider",
            authentication={
                "host": "https://test-jira.com",
                "personal_access_token": "test_token",
            },
        )

    @pytest.fixture
    def jiraonprem_provider(self, context_manager, jiraonprem_config):
        return JiraonpremProvider(context_manager, "test_jiraonprem", jiraonprem_config)

    @patch("requests.post")
    @patch("requests.get")
    def test_create_issue_with_custom_fields_jira_cloud(
        self, mock_get, mock_post, jira_provider
    ):
        """Test that custom fields are properly formatted when creating a Jira issue"""
        # Mock the createmeta response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "projects": [{"issuetypes": [{"name": "Task"}]}]
        }

        # Mock the create request
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"key": "TEST-123", "id": "12345"}

        # Test data
        project_key = "TEST"
        summary = "Test Summary"
        custom_fields = {"customfield_10696": "10"}

        # Call the create method
        result = jira_provider._JiraProvider__create_issue(
            project_key=project_key, summary=summary, custom_fields=custom_fields
        )

        # Verify the request was made with correct payload
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the request body has the correct format for CREATE
        request_body = call_args[1]["json"]
        assert "fields" in request_body
        assert "customfield_10696" in request_body["fields"]
        assert (
            request_body["fields"]["customfield_10696"] == "10"
        )  # Direct value, not set operation
        assert request_body["fields"]["summary"] == summary

        # Verify the result
        assert result["issue"]["key"] == "TEST-123"

    @patch("requests.post")
    @patch("requests.get")
    def test_create_issue_with_custom_fields_jira_onprem(
        self, mock_get, mock_post, jiraonprem_provider
    ):
        """Test that custom fields are properly formatted when creating a Jira On-Prem issue"""
        # Mock the createmeta response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "projects": [{"issuetypes": [{"name": "Task"}]}]
        }

        # Mock the create request
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"key": "TEST-123", "id": "12345"}

        # Test data
        project_key = "TEST"
        summary = "Test Summary"
        custom_fields = {"customfield_10696": "10"}

        # Call the create method
        result = jiraonprem_provider._JiraonpremProvider__create_issue(
            project_key=project_key, summary=summary, custom_fields=custom_fields
        )

        # Verify the request was made with correct payload
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the request body has the correct format for CREATE
        request_body = call_args[1]["json"]
        assert "fields" in request_body
        assert "customfield_10696" in request_body["fields"]
        assert (
            request_body["fields"]["customfield_10696"] == "10"
        )  # Direct value, not set operation
        assert request_body["fields"]["summary"] == summary

        # Verify the result
        assert result["issue"]["key"] == "TEST-123"

    @patch("requests.post")
    @patch("requests.get")
    def test_jiraonprem_ssl_verification_disabled_by_default(
        self, mock_get, mock_post, jiraonprem_provider
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "projects": [{"issuetypes": [{"name": "Task"}]}]
        }
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"key": "TEST-1", "id": "1"}

        jiraonprem_provider._JiraonpremProvider__create_issue(
            project_key="TEST", summary="Test Summary"
        )

        assert mock_post.call_args[1]["verify"] is False

    @patch("requests.post")
    @patch("requests.get")
    def test_jiraonprem_ssl_verification_enabled_via_config(
        self, mock_get, mock_post, context_manager
    ):
        config = ProviderConfig(
            description="Test Jira On-Prem Provider",
            authentication={
                "host": "https://test-jira.com",
                "personal_access_token": "test_token",
                "verify": True,
            },
        )
        provider = JiraonpremProvider(context_manager, "test_jiraonprem_verify", config)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "projects": [{"issuetypes": [{"name": "Task"}]}]
        }
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"key": "TEST-1", "id": "1"}

        provider._JiraonpremProvider__create_issue(
            project_key="TEST", summary="Test Summary"
        )

        assert mock_post.call_args[1]["verify"] is True

    @patch("requests.put")
    @patch("requests.get")
    def test_update_issue_with_custom_fields_jira_cloud(
        self, mock_get, mock_put, jira_provider
    ):
        """Test that custom fields are properly formatted when updating a Jira issue"""
        # Mock the issue key extraction
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"key": "TEST-123"}

        # Mock the update request
        mock_put.return_value.status_code = 204

        # Test data
        issue_id = "12345"
        summary = "Test Summary"
        custom_fields = {"customfield_10696": "10"}

        # Call the update method
        result = jira_provider._JiraProvider__update_issue(
            issue_id=issue_id, summary=summary, custom_fields=custom_fields
        )

        # Verify the request was made with correct payload
        mock_put.assert_called_once()
        call_args = mock_put.call_args

        # Check that the request body has the correct format for UPDATE
        request_body = call_args[1]["json"]
        assert "update" in request_body
        assert "customfield_10696" in request_body["update"]
        assert request_body["update"]["customfield_10696"] == [
            {"set": "10"}
        ]  # Set operation
        assert request_body["update"]["summary"] == [{"set": summary}]

        # Verify the result
        assert result["issue"]["id"] == issue_id
        assert result["issue"]["key"] == "TEST-123"

    @patch("requests.put")
    @patch("requests.get")
    def test_update_issue_with_custom_fields_jira_onprem(
        self, mock_get, mock_put, jiraonprem_provider
    ):
        """Test that custom fields are properly formatted when updating a Jira On-Prem issue"""
        # Mock the issue key extraction
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"key": "TEST-123"}

        # Mock the update request
        mock_put.return_value.status_code = 204

        # Test data
        issue_id = "12345"
        summary = "Test Summary"
        custom_fields = {"customfield_10696": "10"}

        # Call the update method
        result = jiraonprem_provider._JiraonpremProvider__update_issue(
            issue_id=issue_id, summary=summary, custom_fields=custom_fields
        )

        # Verify the request was made with correct payload
        mock_put.assert_called_once()
        call_args = mock_put.call_args

        # Check that the request body has the correct format for UPDATE
        request_body = call_args[1]["json"]
        assert "update" in request_body
        assert "customfield_10696" in request_body["update"]
        assert request_body["update"]["customfield_10696"] == [
            {"set": "10"}
        ]  # Set operation
        assert request_body["update"]["summary"] == [{"set": summary}]

        # Verify the result
        assert result["issue"]["id"] == issue_id
        assert result["issue"]["key"] == "TEST-123"

    @patch("requests.put")
    @patch("requests.get")
    def test_notify_with_issue_id_and_custom_fields(
        self, mock_get, mock_put, jira_provider
    ):
        """Test the _notify method with issue_id and custom fields (update scenario)"""
        # Mock the issue key extraction
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"key": "TEST-123"}

        # Mock the update request
        mock_put.return_value.status_code = 204

        # Test data
        issue_id = "12345"
        summary = "Test Summary"
        custom_fields = {"customfield_10696": "10"}

        # Call the notify method
        result = jira_provider._notify(
            issue_id=issue_id, summary=summary, custom_fields=custom_fields
        )

        # Verify the request was made with correct payload
        mock_put.assert_called_once()
        call_args = mock_put.call_args

        # Check that the request body has the correct format
        request_body = call_args[1]["json"]
        assert "update" in request_body
        assert "customfield_10696" in request_body["update"]
        assert request_body["update"]["customfield_10696"] == [{"set": "10"}]

        # Verify the result
        assert result["issue"]["id"] == issue_id
        assert result["ticket_url"] == f"{jira_provider.jira_host}/browse/TEST-123"

    @patch("requests.post")
    @patch("requests.get")
    def test_notify_without_issue_id_and_custom_fields(
        self, mock_get, mock_post, jira_provider
    ):
        """Test the _notify method without issue_id and custom fields (create scenario)"""
        # Mock the createmeta response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "projects": [{"issuetypes": [{"name": "Task"}]}]
        }

        # Mock the create request
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"key": "TEST-123", "id": "12345"}

        # Test data
        summary = "Test Summary"
        project_key = "TEST"
        custom_fields = {"customfield_10696": "10"}

        # Call the notify method
        result = jira_provider._notify(
            summary=summary,
            description="Test Description",
            project_key=project_key,
            custom_fields=custom_fields,
        )

        # Verify the request was made with correct payload
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that the request body has the correct format for CREATE
        request_body = call_args[1]["json"]
        assert "fields" in request_body
        assert "customfield_10696" in request_body["fields"]
        assert request_body["fields"]["customfield_10696"] == "10"  # Direct value

        # Verify the result
        assert result["issue"]["key"] == "TEST-123"
        assert result["ticket_url"] == f"{jira_provider.jira_host}/browse/TEST-123"

    def test_notify_with_string_kwargs_handling(self, jira_provider):
        """Test that the _notify method handles kwargs properly when it's not a dict"""
        # This test ensures the fix for the "string indices must be integers" error
        # by testing that kwargs handling doesn't fail when kwargs is not a dictionary

        # Mock the necessary methods to avoid actual API calls
        with patch.object(
            jira_provider, "_extract_project_key_from_board_name", return_value="TEST"
        ):
            with patch.object(
                jira_provider,
                "_JiraProvider__create_issue",
                return_value={"issue": {"key": "TEST-123"}},
            ):
                # Test with kwargs that might be passed as a string (edge case)
                result = jira_provider._notify(
                    summary="Test Summary",
                    description="Test Description",
                    project_key="TEST",
                    issue_type="Task",
                )

                # If we get here without the "string indices must be integers" error, the fix worked
                assert result is not None

    @patch("requests.get")
    def test_jiraonprem_query_with_jql(self, mock_get, jiraonprem_provider):
        """Test that a jql query returns only the count of matching issues"""
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"total": 7, "issues": []}

        jql = "project = TEST AND status = Open"
        result = jiraonprem_provider.query(jql=jql)

        # issues is always present, empty here, so a foreach over it in a workflow
        # that left max_results out iterates over nothing
        assert result == {"total": 7, "jql": jql, "issues": []}

        request_url = mock_get.call_args[0][0]
        assert "/rest/api/2/search" in request_url
        assert "maxResults=0" in request_url
        assert "fields" not in request_url
        assert mock_get.call_args[1]["verify"] is False

    @patch("requests.get")
    def test_jiraonprem_query_with_jql_failure(self, mock_get, jiraonprem_provider):
        """Test that a failed jql query raises with Jira's error text"""
        mock_get.return_value.ok = False
        mock_get.return_value.text = "Error in the JQL Query"

        with pytest.raises(ProviderException, match="Error in the JQL Query"):
            jiraonprem_provider.query(jql="status = Nope")

    @patch("requests.get")
    def test_jiraonprem_query_with_ticket_id_fetches_the_issue(
        self, mock_get, jiraonprem_provider
    ):
        """Test that a ticket_id query fetches that issue by key"""
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"key": "TEST-1", "id": "1"}

        result = jiraonprem_provider.query(ticket_id="TEST-1")

        assert result == {"issue": {"key": "TEST-1", "id": "1"}}
        assert "/rest/api/2/issue/TEST-1" in mock_get.call_args[0][0]

    @patch("requests.get")
    def test_jiraonprem_query_with_jql_returning_issues(
        self, mock_get, jiraonprem_provider
    ):
        """Test that max_results asks Jira for the issues and returns them"""
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {
            "total": 2,
            "issues": [{"key": "TEST-1"}, {"key": "TEST-2"}],
        }

        result = jiraonprem_provider.query(jql="status = Open", max_results=50)

        assert result["total"] == 2
        assert [issue["key"] for issue in result["issues"]] == ["TEST-1", "TEST-2"]
        assert "maxResults=50" in mock_get.call_args[0][0]

    @patch("requests.get")
    def test_jiraonprem_query_with_jql_fields(self, mock_get, jiraonprem_provider):
        """Test that fields are passed through, as a string or as a list"""
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"total": 1, "issues": [{}]}

        jiraonprem_provider.query(
            jql="status = Open", max_results=1, fields="summary,status"
        )
        assert "fields=summary%2Cstatus" in mock_get.call_args[0][0]

        jiraonprem_provider.query(
            jql="status = Open", max_results=1, fields=["summary", "status"]
        )
        assert "fields=summary%2Cstatus" in mock_get.call_args[0][0]

    @patch("requests.get")
    def test_jiraonprem_query_with_non_numeric_max_results(
        self, mock_get, jiraonprem_provider
    ):
        """Test that a max_results that is not a number is refused before the request"""
        with pytest.raises(ProviderException, match="non-numeric max_results"):
            jiraonprem_provider.query(jql="status = Open", max_results="fifty")

        mock_get.assert_not_called()
