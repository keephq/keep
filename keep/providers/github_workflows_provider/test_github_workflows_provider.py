"""
Tests for the GitHub Workflows Provider.

Covers:
  - Configuration & auth validation
  - Scope validation (authenticated + actions_read)
  - Alert pulling (_get_alerts)
  - Webhook formatting (_format_alert)
  - Severity and status mapping
  - Edge cases (empty repos, missing fields, success conclusion)
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.github_workflows_provider.github_workflows_provider import (
    GithubWorkflowsProvider,
    GithubWorkflowsProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


def _create_provider(
    token="test-token",
    repos="owner/repo1",
    api_url="https://api.github.com",
) -> GithubWorkflowsProvider:
    """Helper to instantiate a provider with test config."""
    context_manager = MagicMock()
    context_manager.tenant_id = "test-tenant"

    config = ProviderConfig(
        authentication={
            "personal_access_token": token,
            "repositories": repos,
            "api_url": api_url,
        }
    )
    return GithubWorkflowsProvider(context_manager, "test-provider", config)


def _make_workflow_run(
    run_id=12345,
    name="CI",
    run_number=42,
    conclusion="failure",
    branch="main",
    event="push",
    actor="dev-user",
    commit_message="fix: broken tests",
    repo_full_name="owner/repo1",
) -> dict:
    """Create a mock workflow run object."""
    return {
        "id": run_id,
        "name": name,
        "run_number": run_number,
        "conclusion": conclusion,
        "status": "completed",
        "head_branch": branch,
        "event": event,
        "html_url": f"https://github.com/{repo_full_name}/actions/runs/{run_id}",
        "created_at": "2026-03-18T10:00:00Z",
        "updated_at": "2026-03-18T10:05:00Z",
        "actor": {"login": actor},
        "head_commit": {"message": commit_message},
        "repository": {"full_name": repo_full_name},
    }


def _make_webhook_event(run: dict, action="completed") -> dict:
    """Wrap a workflow run into a webhook event payload."""
    return {
        "action": action,
        "workflow_run": run,
        "repository": run.get("repository", {"full_name": "owner/repo1"}),
    }


class TestGithubWorkflowsProviderConfig(unittest.TestCase):
    """Test provider configuration and initialization."""

    def test_basic_config(self):
        provider = _create_provider()
        self.assertEqual(
            provider.authentication_config.personal_access_token, "test-token"
        )
        self.assertEqual(provider.authentication_config.repositories, "owner/repo1")
        self.assertEqual(
            provider.authentication_config.api_url, "https://api.github.com"
        )

    def test_multiple_repos(self):
        provider = _create_provider(repos="owner/repo1, owner/repo2, org/repo3")
        self.assertEqual(provider._repos, ["owner/repo1", "owner/repo2", "org/repo3"])

    def test_empty_repos(self):
        provider = _create_provider(repos="")
        self.assertEqual(provider._repos, [])

    def test_enterprise_api_url(self):
        provider = _create_provider(api_url="https://github.example.com/api/v3")
        self.assertEqual(provider._api_base, "https://github.example.com/api/v3")

    def test_api_url_trailing_slash(self):
        provider = _create_provider(api_url="https://api.github.com/")
        self.assertEqual(provider._api_base, "https://api.github.com")

    def test_provider_display_name(self):
        self.assertEqual(
            GithubWorkflowsProvider.PROVIDER_DISPLAY_NAME, "GitHub Workflows"
        )

    def test_provider_category(self):
        self.assertIn("Developer Tools", GithubWorkflowsProvider.PROVIDER_CATEGORY)

    def test_provider_tags(self):
        self.assertIn("alert", GithubWorkflowsProvider.PROVIDER_TAGS)

    def test_headers(self):
        provider = _create_provider(token="ghp_test123")
        headers = provider._headers
        self.assertEqual(headers["Authorization"], "Bearer ghp_test123")
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")


class TestScopeValidation(unittest.TestCase):
    """Test scope validation logic."""

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_authenticated_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "testuser"}
        mock_get.return_value = mock_resp

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_authenticated_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertIn("401", str(scopes["authenticated"]))

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_actions_read_success(self, mock_get):
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"login": "user"})),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"workflow_runs": []}),
            ),
        ]
        mock_get.side_effect = responses

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])
        self.assertTrue(scopes["actions_read"])

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_actions_read_repo_not_found(self, mock_get):
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"login": "user"})),
            MagicMock(status_code=404),
        ]
        mock_get.side_effect = responses

        provider = _create_provider()
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])
        self.assertIn("not found", scopes["actions_read"])

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_no_repos_configured(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "user"}
        mock_get.return_value = mock_resp

        provider = _create_provider(repos="")
        scopes = provider.validate_scopes()
        self.assertTrue(scopes["authenticated"])
        self.assertIn("No repositories", scopes["actions_read"])


class TestGetAlerts(unittest.TestCase):
    """Test alert pulling from GitHub API."""

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_get_alerts_failure_runs(self, mock_get):
        runs = [
            _make_workflow_run(run_id=1, conclusion="failure"),
            _make_workflow_run(run_id=2, conclusion="success"),
            _make_workflow_run(run_id=3, conclusion="cancelled"),
            _make_workflow_run(run_id=4, conclusion="skipped"),
            _make_workflow_run(run_id=5, conclusion="timed_out"),
        ]
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"workflow_runs": runs}
        mock_get.return_value = mock_resp

        provider = _create_provider()
        alerts = provider._get_alerts()

        # Should get 3 alerts: failure, cancelled, timed_out (not success/skipped)
        self.assertEqual(len(alerts), 3)
        conclusions = [a.labels["conclusion"] for a in alerts]
        self.assertIn("failure", conclusions)
        self.assertIn("cancelled", conclusions)
        self.assertIn("timed_out", conclusions)
        self.assertNotIn("success", conclusions)
        self.assertNotIn("skipped", conclusions)

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_get_alerts_multiple_repos(self, mock_get):
        runs_repo1 = [_make_workflow_run(run_id=1, conclusion="failure")]
        runs_repo2 = [_make_workflow_run(run_id=2, conclusion="failure")]

        mock_get.side_effect = [
            MagicMock(ok=True, json=MagicMock(return_value={"workflow_runs": runs_repo1})),
            MagicMock(ok=True, json=MagicMock(return_value={"workflow_runs": runs_repo2})),
        ]

        provider = _create_provider(repos="owner/repo1,owner/repo2")
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 2)

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_get_alerts_api_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        provider = _create_provider()
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)

    @patch("keep.providers.github_workflows_provider.github_workflows_provider.requests.get")
    def test_get_alerts_empty_runs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"workflow_runs": []}
        mock_get.return_value = mock_resp

        provider = _create_provider()
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)


class TestRunToAlert(unittest.TestCase):
    """Test workflow run to AlertDto conversion."""

    def test_failure_alert(self):
        provider = _create_provider()
        run = _make_workflow_run(conclusion="failure")
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertIn("failure", alert.name)
        self.assertEqual(alert.service, "owner/repo1")
        self.assertEqual(alert.environment, "main")
        self.assertEqual(alert.labels["conclusion"], "failure")
        self.assertEqual(alert.labels["actor"], "dev-user")
        self.assertIn("github_workflows", alert.source)

    def test_cancelled_alert(self):
        provider = _create_provider()
        run = _make_workflow_run(conclusion="cancelled")
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_timed_out_alert(self):
        provider = _create_provider()
        run = _make_workflow_run(conclusion="timed_out")
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertEqual(alert.severity, AlertSeverity.HIGH)

    def test_alert_url(self):
        provider = _create_provider()
        run = _make_workflow_run(run_id=99999)
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertIn("99999", str(alert.url))

    def test_alert_fingerprint(self):
        provider = _create_provider()
        run = _make_workflow_run(run_id=12345)
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertEqual(alert.fingerprint, "github-workflow-owner/repo1-12345")

    def test_alert_description_with_commit(self):
        provider = _create_provider()
        run = _make_workflow_run(commit_message="fix: resolve auth bug")
        alert = provider._run_to_alert(run, "owner/repo1")

        self.assertIn("fix: resolve auth bug", alert.description)

    def test_alert_missing_fields(self):
        """Test handling of workflow run with missing optional fields."""
        provider = _create_provider()
        minimal_run = {
            "id": 1,
            "conclusion": "failure",
            "status": "completed",
        }
        alert = provider._run_to_alert(minimal_run, "owner/repo1")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.labels["actor"], "unknown")


class TestFormatAlert(unittest.TestCase):
    """Test webhook event formatting."""

    def test_format_failure_event(self):
        run = _make_workflow_run(conclusion="failure")
        event = _make_webhook_event(run)

        alert = GithubWorkflowsProvider._format_alert(event)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertIn("failure", alert.name)

    def test_format_success_event(self):
        run = _make_workflow_run(conclusion="success")
        event = _make_webhook_event(run)

        alert = GithubWorkflowsProvider._format_alert(event)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_format_non_completed_action(self):
        """Events with action != 'completed' should be ignored."""
        run = _make_workflow_run(conclusion="failure")
        event = _make_webhook_event(run, action="requested")

        result = GithubWorkflowsProvider._format_alert(event)
        self.assertIsNone(result)

    def test_format_list_of_events(self):
        events = [
            _make_webhook_event(_make_workflow_run(run_id=1, conclusion="failure")),
            _make_webhook_event(_make_workflow_run(run_id=2, conclusion="cancelled")),
        ]

        alerts = GithubWorkflowsProvider._format_alert(events)
        self.assertIsNotNone(alerts)
        self.assertEqual(len(alerts), 2)

    def test_format_list_with_non_completed(self):
        events = [
            _make_webhook_event(_make_workflow_run(run_id=1, conclusion="failure")),
            _make_webhook_event(
                _make_workflow_run(run_id=2, conclusion="failure"), action="in_progress"
            ),
        ]

        alerts = GithubWorkflowsProvider._format_alert(events)
        self.assertIsNotNone(alerts)
        self.assertEqual(len(alerts), 1)

    def test_format_event_with_repo_from_top_level(self):
        """When workflow_run doesn't have repository, use top-level."""
        run = _make_workflow_run(conclusion="failure")
        del run["repository"]
        event = {
            "action": "completed",
            "workflow_run": run,
            "repository": {"full_name": "org/my-repo"},
        }

        alert = GithubWorkflowsProvider._format_alert(event)
        self.assertEqual(alert.service, "org/my-repo")


class TestSeverityMapping(unittest.TestCase):
    """Test severity and status mapping for all conclusions."""

    def test_all_conclusion_severities(self):
        expected = {
            "failure": AlertSeverity.CRITICAL,
            "cancelled": AlertSeverity.WARNING,
            "timed_out": AlertSeverity.HIGH,
            "action_required": AlertSeverity.INFO,
            "startup_failure": AlertSeverity.CRITICAL,
            "success": AlertSeverity.INFO,
        }
        for conclusion, severity in expected.items():
            self.assertEqual(
                GithubWorkflowsProvider.SEVERITIES_MAP[conclusion],
                severity,
                f"Severity mismatch for conclusion '{conclusion}'",
            )

    def test_all_conclusion_statuses(self):
        expected = {
            "failure": AlertStatus.FIRING,
            "cancelled": AlertStatus.FIRING,
            "timed_out": AlertStatus.FIRING,
            "action_required": AlertStatus.PENDING,
            "startup_failure": AlertStatus.FIRING,
            "success": AlertStatus.RESOLVED,
        }
        for conclusion, status in expected.items():
            self.assertEqual(
                GithubWorkflowsProvider.STATUS_MAP[conclusion],
                status,
                f"Status mismatch for conclusion '{conclusion}'",
            )


class TestSimulateAlert(unittest.TestCase):
    """Test alert simulation."""

    def test_simulate_returns_valid_event(self):
        event = GithubWorkflowsProvider.simulate_alert()

        self.assertIn("action", event)
        self.assertEqual(event["action"], "completed")
        self.assertIn("workflow_run", event)

        run = event["workflow_run"]
        self.assertIn("id", run)
        self.assertIn("name", run)
        self.assertIn("conclusion", run)
        self.assertIn(run["conclusion"], ["failure", "cancelled", "timed_out"])

    def test_simulated_event_can_be_formatted(self):
        event = GithubWorkflowsProvider.simulate_alert()
        alert = GithubWorkflowsProvider._format_alert(event)

        self.assertIsNotNone(alert)
        self.assertIn(alert.severity, [AlertSeverity.CRITICAL, AlertSeverity.WARNING, AlertSeverity.HIGH])


if __name__ == "__main__":
    unittest.main()
