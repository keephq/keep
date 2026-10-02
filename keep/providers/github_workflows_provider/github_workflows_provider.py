"""
GithubWorkflowsProvider is a provider that monitors GitHub Actions workflow runs
and surfaces failures as alerts in Keep.

Supports:
  - Polling: _get_alerts() fetches failed/cancelled workflow runs via the GitHub API
  - Webhook: _format_alert() parses incoming `workflow_run` webhook payloads
  - GitHub Enterprise Server via configurable api_url
"""

import dataclasses
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GithubWorkflowsProviderAuthConfig:
    """Authentication configuration for the GitHub Workflows provider."""

    personal_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitHub Personal Access Token (classic or fine-grained)",
            "sensitive": True,
        }
    )

    repositories: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Comma-separated list of repositories to monitor (e.g. 'owner/repo1,owner/repo2')",
            "hint": "owner/repo1,owner/repo2",
        },
    )

    api_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "GitHub API base URL (for GitHub Enterprise Server)",
            "hint": "https://api.github.com (default) or https://github.example.com/api/v3",
        },
        default="https://api.github.com",
    )


class GithubWorkflowsProvider(BaseProvider):
    """
    Monitor GitHub Actions workflow runs and receive alerts for failures.

    Pulls workflow run failures from the GitHub Actions API and/or receives
    webhook events when workflow runs complete with failure/cancellation.
    """

    PROVIDER_DISPLAY_NAME = "GitHub Workflows"
    PROVIDER_CATEGORY = ["Developer Tools"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated and can access the GitHub API",
            mandatory=True,
            alias="Authenticated",
        ),
        ProviderScope(
            name="actions_read",
            description="User can read workflow runs from configured repositories",
            mandatory=True,
            alias="Actions Read",
        ),
    ]

    FINGERPRINT_FIELDS = ["id"]

    SEVERITIES_MAP = {
        "failure": AlertSeverity.CRITICAL,
        "cancelled": AlertSeverity.WARNING,
        "timed_out": AlertSeverity.HIGH,
        "action_required": AlertSeverity.INFO,
        "startup_failure": AlertSeverity.CRITICAL,
        "success": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "failure": AlertStatus.FIRING,
        "cancelled": AlertStatus.FIRING,
        "timed_out": AlertStatus.FIRING,
        "action_required": AlertStatus.PENDING,
        "startup_failure": AlertStatus.FIRING,
        "success": AlertStatus.RESOLVED,
    }

    webhook_description = "Receive GitHub Actions workflow_run events"
    webhook_markdown = """
To send GitHub Actions workflow run events to Keep, configure a webhook in your repository:

1. Go to your repository on GitHub → **Settings** → **Webhooks** → **Add webhook**.
2. Set the **Payload URL** to: `{keep_webhook_api_url}`
3. Set **Content type** to `application/json`.
4. Under **Secret**, enter a secret of your choice (optional).
5. Under **Which events would you like to trigger this webhook?**, select **Let me select individual events**.
6. Check **Workflow runs** and uncheck everything else.
7. Under **Headers**, add: `X-API-KEY: {api_key}`
8. Click **Add webhook**.

Keep will now receive alerts whenever a workflow run completes with a failure, cancellation, or timeout.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """No resources to dispose."""
        pass

    def validate_config(self):
        self.authentication_config = GithubWorkflowsProviderAuthConfig(
            **self.config.authentication
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def _api_base(self) -> str:
        url = self.authentication_config.api_url.rstrip("/")
        if not url:
            url = "https://api.github.com"
        return url

    @property
    def _repos(self) -> list[str]:
        raw = self.authentication_config.repositories or ""
        return [r.strip() for r in raw.split(",") if r.strip()]

    def _api_get(self, path: str, params: dict | None = None) -> requests.Response:
        url = f"{self._api_base}/{path.lstrip('/')}"
        response = requests.get(url, headers=self._headers, params=params, timeout=30)
        return response

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}

        # Check authentication
        try:
            resp = self._api_get("/user")
            if resp.status_code == 200:
                scopes["authenticated"] = True
            else:
                scopes["authenticated"] = (
                    f"Authentication failed (HTTP {resp.status_code})"
                )
                scopes["actions_read"] = "Cannot verify — not authenticated"
                return scopes
        except Exception as e:
            scopes["authenticated"] = str(e)
            scopes["actions_read"] = "Cannot verify — not authenticated"
            return scopes

        # Check actions read on first configured repo
        repos = self._repos
        if not repos:
            scopes["actions_read"] = "No repositories configured"
            return scopes

        try:
            resp = self._api_get(
                f"/repos/{repos[0]}/actions/runs", params={"per_page": 1}
            )
            if resp.status_code == 200:
                scopes["actions_read"] = True
            elif resp.status_code == 404:
                scopes["actions_read"] = (
                    f"Repository '{repos[0]}' not found or no access"
                )
            else:
                scopes["actions_read"] = (
                    f"Cannot read workflow runs (HTTP {resp.status_code})"
                )
        except Exception as e:
            scopes["actions_read"] = str(e)

        return scopes

    # ------------------------------------------------------------------
    # Alert pulling
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull failed/cancelled workflow runs from all configured repositories.

        Returns recent workflow runs (last 100 per repo) that ended with a
        non-success conclusion: failure, cancelled, timed_out, action_required,
        or startup_failure.
        """
        alerts: list[AlertDto] = []

        for repo in self._repos:
            try:
                self.logger.info(f"Fetching workflow runs from {repo}")
                resp = self._api_get(
                    f"/repos/{repo}/actions/runs",
                    params={
                        "per_page": 100,
                        "status": "completed",
                    },
                )

                if not resp.ok:
                    self.logger.error(
                        f"Failed to fetch runs from {repo}: HTTP {resp.status_code}"
                    )
                    continue

                data = resp.json()
                runs = data.get("workflow_runs", [])

                failed_count = 0
                for run in runs:
                    conclusion = run.get("conclusion", "")
                    if conclusion in ("success", "skipped", "neutral", None):
                        continue

                    alert = self._run_to_alert(run, repo)
                    if alert:
                        alerts.append(alert)
                        failed_count += 1

                self.logger.info(
                    f"Found {failed_count} failed runs in {repo}"
                )

            except Exception as e:
                self.logger.error(
                    f"Error fetching workflow runs from {repo}",
                    extra={"error": str(e)},
                )

        return alerts

    def _run_to_alert(self, run: dict, repo: str) -> AlertDto | None:
        """Convert a GitHub workflow run object to an AlertDto."""
        conclusion = run.get("conclusion", "failure")
        run_id = run.get("id")
        workflow_name = run.get("name", "Unknown Workflow")
        run_number = run.get("run_number", "?")
        branch = run.get("head_branch", "unknown")
        event = run.get("event", "unknown")
        html_url = run.get("html_url", "")
        created_at = run.get("created_at", "")
        updated_at = run.get("updated_at", "")
        actor = run.get("actor", {})
        actor_login = actor.get("login", "unknown") if actor else "unknown"
        head_commit = run.get("head_commit", {}) or {}
        commit_message = head_commit.get("message", "")

        severity = self.SEVERITIES_MAP.get(conclusion, AlertSeverity.WARNING)
        status = self.STATUS_MAP.get(conclusion, AlertStatus.FIRING)

        description = (
            f"Workflow **{workflow_name}** #{run_number} {conclusion} "
            f"on branch `{branch}` (trigger: {event})"
        )
        if commit_message:
            first_line = commit_message.split("\n")[0][:120]
            description += f"\nCommit: {first_line}"

        return AlertDto(
            id=str(run_id),
            name=f"{repo}: {workflow_name} #{run_number} {conclusion}",
            status=status,
            severity=severity,
            lastReceived=updated_at or datetime.now(timezone.utc).isoformat(),
            source=["github_workflows"],
            message=f"Workflow '{workflow_name}' #{run_number} {conclusion}",
            description=description,
            description_format="markdown",
            url=html_url,
            service=repo,
            environment=branch,
            labels={
                "repo": repo,
                "workflow_name": workflow_name,
                "run_number": str(run_number),
                "branch": branch,
                "event": event,
                "conclusion": conclusion,
                "actor": actor_login,
            },
            fingerprint=f"github-workflow-{repo}-{run_id}",
        )

    # ------------------------------------------------------------------
    # Webhook (format incoming events)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list[dict],
        provider_instance: "BaseProvider" = None,
    ) -> AlertDto | list[AlertDto] | None:
        """
        Format an incoming GitHub workflow_run webhook event into AlertDto(s).

        GitHub sends a workflow_run event with action='completed' when a run
        finishes. We only create alerts for non-success conclusions.
        """
        if isinstance(event, list):
            alerts = []
            for e in event:
                result = GithubWorkflowsProvider._format_single_event(e)
                if result:
                    alerts.append(result)
            return alerts if alerts else None

        return GithubWorkflowsProvider._format_single_event(event)

    @staticmethod
    def _format_single_event(event: dict) -> AlertDto | None:
        """Format a single webhook event."""
        action = event.get("action", "")
        workflow_run = event.get("workflow_run", event)

        # Only process completed runs
        if action and action != "completed":
            return None

        conclusion = workflow_run.get("conclusion", "")

        # Map conclusion to severity/status
        severity = GithubWorkflowsProvider.SEVERITIES_MAP.get(
            conclusion, AlertSeverity.WARNING
        )
        status = GithubWorkflowsProvider.STATUS_MAP.get(
            conclusion, AlertStatus.FIRING
        )

        # If success, mark as resolved
        if conclusion == "success":
            status = AlertStatus.RESOLVED

        run_id = workflow_run.get("id", "unknown")
        workflow_name = workflow_run.get("name", "Unknown Workflow")
        run_number = workflow_run.get("run_number", "?")

        repo_data = workflow_run.get("repository", event.get("repository", {})) or {}
        repo = repo_data.get("full_name", "unknown/unknown")

        branch = workflow_run.get("head_branch", "unknown")
        event_trigger = workflow_run.get("event", "unknown")
        html_url = workflow_run.get("html_url", "")
        updated_at = workflow_run.get("updated_at", "")
        actor = workflow_run.get("actor", {}) or {}
        actor_login = actor.get("login", "unknown")

        head_commit = workflow_run.get("head_commit", {}) or {}
        commit_message = head_commit.get("message", "")

        description = (
            f"Workflow **{workflow_name}** #{run_number} {conclusion} "
            f"on branch `{branch}` (trigger: {event_trigger})"
        )
        if commit_message:
            first_line = commit_message.split("\n")[0][:120]
            description += f"\nCommit: {first_line}"

        return AlertDto(
            id=str(run_id),
            name=f"{repo}: {workflow_name} #{run_number} {conclusion}",
            status=status,
            severity=severity,
            lastReceived=updated_at or datetime.now(timezone.utc).isoformat(),
            source=["github_workflows"],
            message=f"Workflow '{workflow_name}' #{run_number} {conclusion}",
            description=description,
            description_format="markdown",
            url=html_url,
            service=repo,
            environment=branch,
            labels={
                "repo": repo,
                "workflow_name": workflow_name,
                "run_number": str(run_number),
                "branch": branch,
                "event": event_trigger,
                "conclusion": conclusion,
                "actor": actor_login,
            },
            fingerprint=f"github-workflow-{repo}-{run_id}",
        )

    # ------------------------------------------------------------------
    # Simulate alert (for UI testing)
    # ------------------------------------------------------------------

    @classmethod
    def simulate_alert(cls) -> dict:
        import random

        conclusions = ["failure", "cancelled", "timed_out"]
        workflows = ["CI", "Release", "Deploy", "Lint", "Test"]
        repos = ["acme/backend", "acme/frontend", "acme/infra"]
        branches = ["main", "develop", "feature/auth", "fix/hotfix-123"]

        conclusion = random.choice(conclusions)
        repo = random.choice(repos)

        return {
            "action": "completed",
            "workflow_run": {
                "id": random.randint(10000000, 99999999),
                "name": random.choice(workflows),
                "run_number": random.randint(100, 9999),
                "conclusion": conclusion,
                "status": "completed",
                "head_branch": random.choice(branches),
                "event": random.choice(["push", "pull_request", "schedule"]),
                "html_url": f"https://github.com/{repo}/actions/runs/{random.randint(10000000, 99999999)}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "actor": {"login": "developer"},
                "head_commit": {
                    "message": f"fix: resolve {random.choice(['auth', 'db', 'api', 'cache'])} issue"
                },
            },
            "repository": {"full_name": repo},
        }

    # ------------------------------------------------------------------
    # Notify (trigger workflow dispatch)
    # ------------------------------------------------------------------

    def _notify(
        self,
        github_url: str = "",
        github_method: str = "GET",
        workflow: str = "",
        repo: str = "",
        ref: str = "main",
        inputs: dict | None = None,
        **kwargs,
    ):
        """
        Trigger a GitHub Actions workflow dispatch or make arbitrary API calls.

        For workflow dispatch, provide `workflow` and `repo` parameters.
        For arbitrary API calls, provide `github_url` and `github_method`.
        """
        if workflow and repo:
            # Workflow dispatch
            url = f"{self._api_base}/repos/{repo}/actions/workflows/{workflow}/dispatches"
            payload = {"ref": ref}
            if inputs:
                payload["inputs"] = inputs

            response = requests.post(
                url, headers=self._headers, json=payload, timeout=30
            )
            self.logger.info(
                f"Triggered workflow {workflow} on {repo}@{ref}: {response.status_code}"
            )
            return {
                "status": response.ok,
                "status_code": response.status_code,
            }

        if github_url:
            # Arbitrary API call (backward-compatible)
            method = github_method.upper()
            response = requests.request(
                method, github_url, headers=self._headers, timeout=30, **kwargs
            )
            try:
                body = response.json()
            except Exception:
                body = response.text
            return {
                "status": response.ok,
                "status_code": response.status_code,
                "body": body,
            }

        raise ValueError("Either 'workflow'+'repo' or 'github_url' must be provided")


if __name__ == "__main__":
    import os

    github_token = os.environ.get("GITHUB_TOKEN", "")
    repos = os.environ.get("GITHUB_REPOS", "keephq/keep")

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    provider = GithubWorkflowsProvider(
        context_manager,
        "test",
        ProviderConfig(
            authentication={
                "personal_access_token": github_token,
                "repositories": repos,
            }
        ),
    )

    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} failed workflow runs:")
    for alert in alerts[:5]:
        print(f"  - {alert.name} ({alert.severity})")
