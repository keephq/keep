"""
GithubProvider is a provider that interacts with GitHub.
"""

import dataclasses

import pydantic
from github import Github
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class GithubProviderAuthConfig:
    """
    GithubProviderAuthConfig is a class that represents the authentication configuration for the GithubProvider.
    """

    access_token: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitHub Access Token",
            "sensitive": True,
        }
    )


class GithubProvider(BaseProvider):
    """
    Enrich alerts with data from GitHub.
    """

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
    💡 For more details on how to configure GitHub to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/github-provider).

    To send alerts from GitHub to Keep, Use the following webhook url to configure GitHub send alerts to Keep:

    1. Github supports the following webhook events
    - Repository webhooks 
    - Organization webhooks
    - GitHub Marketplace webhooks
    - GitHub Sponsors webhooks
    - GitHub Apps webhooks
    2. Follow this [guide](https://docs.github.com/en/webhooks/using-webhooks/creating-webhooks) from GitHub to create a webhook according to your requirements.
    3. Set the Payload URL as {keep_webhook_api_url}?api_key={api_key}.
    4. Set the Content type as 'application/json'.
    5. Configure the rest of the settings as per your requirements.
    6. Add the webhook.
    """

    PROVIDER_DISPLAY_NAME = "GitHub"
    PROVIDER_CATEGORY = ["Developer Tools"]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="get_last_commits",
            func_name="get_last_commits",
            description="Get the N last commits from a GitHub repository",
            type="view",
        ),
        ProviderMethod(
            name="get_last_releases",
            func_name="get_last_releases",
            description="Get the N last releases and their changelog from a GitHub repository",
            type="view",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.client = self.__generate_client()

    def get_last_commits(self, repository: str, n: int = 10):
        self.logger.info(f"Getting last {n} commits from {repository}")
        repo = self.client.get_repo(repository)
        commits = repo.get_commits()
        self.logger.info(f"Found {commits.totalCount} commits")
        return [commit.raw_data for commit in commits[:n]]

    def get_last_releases(self, repository: str, n: int = 10):
        self.logger.info(f"Getting last {n} releases from {repository}")
        repo = self.client.get_repo(repository)
        releases = repo.get_releases()
        self.logger.info(f"Found {releases.totalCount} releases")
        return [release.raw_data for release in releases[:n]]

    def __generate_client(self):
        # Should get an access token once we have a real use case for GitHub provider
        if self.authentication_config.access_token:
            client = Github(self.authentication_config.access_token)
        else:
            client = Github()
        return client

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

    def validate_config(self):
        self.authentication_config = GithubProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        
        """
        Webhook events and payloads for GitHub:
        https://docs.github.com/en/webhooks/webhook-events-and-payloads
        """

        ref = event.get("ref", {})
        if isinstance(ref, str):
            ref = {"ref": ref}

        comment = event.get("comment", {})
        if isinstance(comment, str):
            comment = {"comment": comment}

        workflow = event.get("workflow", {})
        if isinstance(workflow, str):
            workflow = {"workflow": workflow}

        sender = event.get("sender", {})
        name = sender.get("login", "Unable to fetch sender name")
        
        lastReceived = datetime.now(timezone.utc).isoformat()

        alert_data = {
            "name": name,
            "lastReceived": lastReceived,
            "action": event.get("action", "Unable to fetch action"),
            "enterprise": event.get("enterprise", {}),
            "installation": event.get("installation", {}),
            "organization": event.get("organization", {}),
            "repository": event.get("repository", {}),
            "sender": event.get("sender", {}),
            "rule": event.get("rule", {}),
            "check_run": event.get("check_run", {}),
            "check_suite": event.get("check_suite", {}),
            "alert": event.get("alert", {}),
            "commit_oid": event.get("commit_oid", {}),
            "ref": ref,
            "comment": comment,
            "description": event.get("description", event.get("action", "Unable to fetch description")),
            "master_branch": event.get("master_branch", "Unable to fetch master_branch"),
            "pusher_type": event.get("pusher_type", "Unable to fetch pusher_type"),
            "ref_type": event.get("ref_type", "Unable to fetch ref_type"),
            "definition": event.get("definition", {}),
            "new_property_values": event.get("new_property_values", []),
            "old_property_values": event.get("old_property_values", []),
            "key": event.get("key", {}),
            "deployment": event.get("deployment", {}),
            "workflow": workflow,
            "workflow_run": event.get("workflow_run", {}),
            "environment": event.get("environment", "Unable to fetch environment"),
            "event_name": event.get("event", "Unable to fetch event_name"),
            "deployment_callback_url": event.get("deployment_callback_url", "Unable to fetch deployment_callback_url"),
            "pull_requests": event.get("pull_requests", []),
            "approver": event.get("approver", {}),
            "reviewers": event.get("reviewers", []),
            "since": event.get("since", "Unable to fetch since"),
            "workflow_job_run": event.get("workflow_job_run", {}),
            "workflow_job_runs": event.get("workflow_job_runs", []),
            "deployment_status": event.get("deployment_status", {}),
            "answer": event.get("answer", {}),
            "discussion": event.get("discussion", {}),
            "forkee": event.get("forkee", {}),
            "pages": event.get("pages", []),
            "repositories": event.get("repositories", []),
            "requester": event.get("requester", {}),
            "repositories_added": event.get("repositories_added", []),
            "repositories_removed": event.get("repositories_removed", []),
            "repository_selection": event.get("repository_selection", "Unable to fetch repository_selection"),
            "account": event.get("account", {}),
            "changes": event.get("changes", {}),
            "target_type": event.get("target_type", "Unable to fetch target_type"),
            "issue": event.get("issue", {}),
            "assignee": event.get("assignee", {}),
            "label": event.get("label", {}),
            "effective_date": event.get("effective_date", "Unable to fetch effective_date"),
            "marketplace_purchase": event.get("marketplace_purchase", {}),
            "previous_marketplace_purchase": event.get("previous_marketplace_purchase", {}),
            "member": event.get("member", {}),
            "scope": event.get("scope", "Unable to fetch scope"),
            "team": event.get("team", {}),
            "merge_group": event.get("merge_group", {}),
            "hook": event.get("hook", {}),
            "hook_id": event.get("hook_id", "Unable to fetch hook_id"),
            "milestone": event.get("milestone", {}),
            "blocked_user": event.get("blocked_user", {}),
            "membership": event.get("membership", {}),
            "package": event.get("package", {}),
            "build": event.get("build", {}),
            "page_build_id": event.get("id", "Unable to fetch id"),
            "personal_access_token_request": event.get("personal_access_token_request", {}),
            "zen": event.get("zen", "Unable to fetch zen"),
            "project_card": event.get("project_card", {}),
            "project": event.get("project", {}),
            "project_column": event.get("project_column", {}),
            "projects_v2": event.get("projects_v2", {}),
            "projects_v2_item": event.get("projects_v2_item", {}),
            "projects_v2_status_update": event.get("projects_v2_status_update", {}),
            "pr_number": event.get("number", "Unable to fetch number"),
            "pull_request": event.get("pull_request", {}),
            "pr_review": event.get("review", {}),
            "pr_thread": event.get("thread", {}),
            "push_after": event.get("after", "Unable to fetch after"),
            "base_ref": event.get("base_ref", "Unable to fetch base_ref"),
            "push_before": event.get("before", "Unable to fetch before"),
            "commits": event.get("commits", []),
            "compare_before_and_after_push": event.get("compare", "Unable to fetch compare"),
            "created_ref": event.get("created", "Unable to fetch created"),
            "deleted_ref": event.get("deleted", "Unable to fetch deleted"),
            "forced_push": event.get("forced", "Unable to fetch forced"),
            "head_commit": event.get("head_commit", {}),
            "pusher": event.get("pusher", {}),
            "registry_package": event.get("registry_package", {}),
            "release": event.get("release", {}),
            "repository_advisory": event.get("repository_advisory", {}),
            "client_payload": event.get("client_payload", {}),
            "repository_import_status": event.get("status", "Unable to fetch status"),
            "repository_ruleset": event.get("repository_ruleset", {}),
            "secret_scanning_alert_location": event.get("location", {}),
            "secret_scanning_type": event.get("type", "Unable to fetch secret scanning type"),
            "secret_scanning_source": event.get("source", "Unable to fetch secret scanning source"),
            "secret_scanning_started_at": event.get("started_at", "Unable to fetch secret scanning started_at"),
            "secret_scanning_completed_at": event.get("completed_at", "Unable to fetch secret scanning completed_at"),
            "secret_types": event.get("secret_types", []),
            "secret_scanning_custom_pattern_name": event.get("custom_pattern_name", "Unable to fetch secret scanning custom pattern name"),
            "secret_scanning_custom_pattern_scope": event.get("custom_pattern_scope", "Unable to fetch secret scanning custom pattern scope"),
            "security_advisory": event.get("security_advisory", {}),
            "sponsorship": event.get("sponsorship", {}),
            "starred_at": event.get("starred_at", "Unable to fetch starred_at"),
            "avatar_url": event.get("avatar_url", "Unable to fetch avatar_url"),
            "branches": event.get("branches", []),
            "commit": event.get("commit", {}),
            "context": event.get("context", "Unable to fetch context"),
            "created_at": event.get("created_at", "Unable to fetch created_at"),
            "status_id": event.get("id", "Unable to fetch status id"),
            "status_name": event.get("name", "Unable to fetch name"),
            "sha": event.get("sha", "Unable to fetch sha"),
            "state": event.get("state", "Unable to fetch state"),
            "target_url": event.get("target_url", "Unable to fetch target_url"),
            "updated_at": event.get("updated_at", "Unable to fetch updated_at"),
            "parent_issue_id": event.get("parent_issue_id", "Unable to fetch parent_issue_id"),
            "parent_issue": event.get("parent_issue", {}),
            "parent_issue_repo": event.get("parent_issue_repo", {}),
            "sub_issue_id": event.get("sub_issue_id", "Unable to fetch sub_issue_id"),
            "sub_issue": event.get("sub_issue", {}),
            "inputs": event.get("inputs", {}),
            "workflow_job": event.get("workflow_job", {}),
            "source": ["github"],
        }

        # Filter out empty values
        alert_data = {k: v for k, v in alert_data.items() if v}

        alert = AlertDto(**alert_data)

        return alert


class GithubStarsProvider(GithubProvider):
    """
    GithubStarsProvider is a class that provides a way to read stars from a GitHub repository.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def _query(
        self,
        repository: str,
        previous_stars_count: int = 0,
        last_stargazer: str = "",
        **kwargs: dict,
    ) -> dict:
        repo = self.client.get_repo(repository)
        stars_count = repo.stargazers_count
        new_stargazers = []

        if not previous_stars_count:
            previous_stars_count = 0

        self.logger.debug(f"Previous stargazers: {previous_stars_count}")
        self.logger.debug(f"New stargazers: {stars_count - int(previous_stars_count)}")

        stargazers_with_dates = []
        # If we have the last stargazer login name, use it as index
        if last_stargazer:
            stargazers_with_dates = list(repo.get_stargazers_with_dates())
            last_stargazer_index = next(
                (
                    i
                    for i, item in enumerate(stargazers_with_dates)
                    if item.user.login == last_stargazer
                ),
                -1,
            )
            if last_stargazer_index == -1:
                stargazers_with_dates = []
            else:
                stargazers_with_dates = stargazers_with_dates[
                    last_stargazer_index + 1 :
                ]
        # If we dont, use the previous stars count as an index
        elif previous_stars_count and int(previous_stars_count) > 0:
            stargazers_with_dates = list(repo.get_stargazers_with_dates())[
                int(previous_stars_count) :
            ]

        # Iterate new stargazers if there are any
        for stargazer in stargazers_with_dates:
            new_stargazers.append(
                {
                    "username": stargazer.user.login,
                    "starred_at": str(stargazer.starred_at),
                }
            )
            self.logger.debug(f"New stargazer: {stargazer.user.login}")

        # Save last stargazer name so we can use it next iteration
        last_stargazer = (
            new_stargazers[-1]["username"]
            if len(new_stargazers) >= 1
            else last_stargazer
        )

        return {
            "stars": stars_count,
            "new_stargazers": new_stargazers,
            "new_stargazers_count": len(new_stargazers),
            "last_stargazer": last_stargazer,
        }


if __name__ == "__main__":
    import os

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    github_provider = GithubProvider(
        context_manager,
        "test",
        ProviderConfig(authentication={"access_token": os.environ.get("GITHUB_PAT")}),
    )

    result = github_provider.get_last_commits("keephq/keep", 10)
    print(result)
