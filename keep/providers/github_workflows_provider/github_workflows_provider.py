"""
GitHub Workflows Provider is a provider that monitors GitHub Actions workflow runs.
"""

import dataclasses
from datetime import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GithubWorkflowsProviderAuthConfig:
    """
    GithubWorkflowsProviderAuthConfig is a class that represents the authentication configuration for the GithubWorkflowsProvider.
    """

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitHub Access Token (PAT)",
            "sensitive": True,
        }
    )

    repositories: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Comma-separated list of repositories to monitor (e.g., 'owner/repo1,owner/repo2')",
            "sensitive": False,
        }
    )

    github_base_url: str = dataclasses.field(
        default="https://api.github.com",
        metadata={
            "required": False,
            "description": "GitHub API Base URL (for GitHub Enterprise Server)",
            "sensitive": False,
        },
    )


class GithubWorkflowsProvider(BaseProvider):
    """
    Monitor GitHub Actions workflow runs and alert on failures.
    """

    PROVIDER_DISPLAY_NAME = "GitHub Workflows"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Developer Tools"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="actions:read",
            description="Read access to GitHub Actions workflows and runs",
        ),
    ]

    # Map workflow run conclusions to Keep alert severities
    SEVERITY_MAP = {
        "failure": AlertSeverity.CRITICAL,
        "timed_out": AlertSeverity.HIGH,
        "cancelled": AlertSeverity.LOW,
        "action_required": AlertSeverity.WARNING,
    }

    # Map workflow run conclusions to Keep alert statuses
    STATUS_MAP = {
        "failure": AlertStatus.FIRING,
        "timed_out": AlertStatus.FIRING,
        "success": AlertStatus.RESOLVED,
        "cancelled": AlertStatus.FIRING,
        "action_required": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for GitHub Workflows provider.
        """
        self.authentication_config = GithubWorkflowsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider by testing API access.
        """
        self.logger.info("Validating GitHub Workflows provider scopes")
        try:
            # Test with the first repository to validate token works
            repos = [repo.strip() for repo in self.authentication_config.repositories.split(",")]
            if not repos:
                return {"actions:read": "No repositories configured"}

            first_repo = repos[0]
            url = f"{self.authentication_config.github_base_url}/repos/{first_repo}/actions/runs"
            headers = self.__get_auth_headers()
            
            response = requests.get(url, headers=headers, params={"per_page": 1})

            if response.status_code == 200:
                self.logger.info("Successfully validated scopes")
                return {"actions:read": True}
            else:
                error_msg = f"Failed to validate scopes: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                return {"actions:read": error_msg}

        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": e})
            return {"actions:read": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from GitHub Actions workflow runs.
        """
        self.logger.info("Getting alerts from GitHub Actions workflow runs")
        alerts = []
        
        repos = [repo.strip() for repo in self.authentication_config.repositories.split(",")]
        
        for repo in repos:
            if not repo:
                continue
                
            try:
                self.logger.info(f"Fetching workflow runs for repository: {repo}")
                repo_alerts = self.__get_workflow_runs(repo)
                alerts.extend(repo_alerts)
                self.logger.info(f"Found {len(repo_alerts)} alerts for {repo}")
            except Exception as e:
                self.logger.error(f"Error fetching workflow runs for {repo}: {e}")
                continue
        
        self.logger.info(f"Total alerts found: {len(alerts)}")
        return alerts

    def __get_workflow_runs(self, repo: str) -> list[AlertDto]:
        """
        Get workflow runs for a specific repository.
        """
        alerts = []

        url = f"{self.authentication_config.github_base_url}/repos/{repo}/actions/runs"
        headers = self.__get_auth_headers()

        # GitHub API uses the 'status' parameter for both run status AND conclusion
        # values. The 'conclusion' query parameter is ignored by the API.
        # We must make separate requests for each conclusion type we care about.
        failure_statuses = ["failure", "timed_out", "cancelled", "action_required"]

        for conclusion in failure_statuses:
            params = {
                "status": conclusion,
                "per_page": 100,  # GitHub's maximum per page
            }

            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()

                data = response.json()
                workflow_runs = data.get("workflow_runs", [])

                for run in workflow_runs:
                    alert = self.__convert_workflow_run_to_alert(run, repo)
                    if alert:
                        alerts.append(alert)

            except requests.RequestException as e:
                self.logger.error(
                    f"Error fetching workflow runs for {repo} "
                    f"(status={conclusion}): {e}"
                )
                raise

        return alerts

    def __convert_workflow_run_to_alert(self, run: dict, repo: str) -> AlertDto:
        """
        Convert a GitHub workflow run to a Keep AlertDto.
        """
        conclusion = run.get("conclusion", "").lower()
        workflow_name = run.get("name", "Unknown Workflow")
        
        # Get severity and status from our mappings
        severity = self.SEVERITY_MAP.get(conclusion, AlertSeverity.INFO)
        status = self.STATUS_MAP.get(conclusion, AlertStatus.FIRING)
        
        # Create fingerprint for deduplication
        workflow_id = run.get("workflow_id", "unknown")
        run_number = run.get("run_number", "unknown")
        fingerprint = f"{repo}:{workflow_id}:{run_number}"
        
        # Parse the run's created/updated time
        updated_at = run.get("updated_at", run.get("created_at", datetime.now().isoformat()))
        
        alert = AlertDto(
            id=str(run.get("id")),
            name=workflow_name,
            description=f"{workflow_name} failed in {repo}",
            severity=severity,
            status=status,
            lastReceived=updated_at,
            source=["github_workflows"],
            url=run.get("html_url"),
            fingerprint=fingerprint,
            # Additional workflow-specific fields
            repository=repo,
            workflow_id=str(workflow_id),
            run_number=run_number,
            conclusion=conclusion,
            head_branch=run.get("head_branch"),
            head_sha=run.get("head_sha"),
            actor=run.get("actor", {}).get("login") if run.get("actor") else None,
            event=run.get("event"),
            run_started_at=run.get("run_started_at"),
            workflow_url=run.get("workflow_url"),
        )
        
        return alert

    def __get_auth_headers(self) -> dict:
        """
        Get the authentication headers for GitHub API requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Test configuration
    access_token = os.getenv("GITHUB_ACCESS_TOKEN")
    repositories = os.getenv("GITHUB_REPOSITORIES", "octocat/Hello-World")

    config = ProviderConfig(
        description="GitHub Workflows Provider",
        authentication={
            "access_token": access_token,
            "repositories": repositories,
        }
    )

    provider = GithubWorkflowsProvider(context_manager, "github_workflows_test", config)
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")
    for alert in alerts:
        print(f"Alert: {alert.name} - {alert.status} - {alert.severity}")
