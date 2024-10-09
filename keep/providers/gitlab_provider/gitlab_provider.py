"""
GitlabProvider is a class that implements the BaseRunBookProvider interface for GitLab updates.
"""

import dataclasses
import urllib.parse

import pydantic
import requests
from requests import HTTPError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseRunBookProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GitlabProviderAuthConfig:
    """GitLab authentication configuration."""

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitLab Host",
            "sensitive": False,
            "hint": "example.gitlab.com",
        }
    )

    personal_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitLab Personal Access Token",
            "sensitive": True,
            "documentation_url": "https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html",
        }
    )
    repository: str = dataclasses.field(
        metadata={
            "description": "GitHub Repository Id",
            "sensitive": False,
        },
        default=None,
    )
    md_path: str = dataclasses.field(
        metadata={
            "description": "Path to .md files in the repository",
            "sensitive": False,
        },
        default=None,
    )


class GitlabProvider(BaseRunBookProvider):
    """Enrich alerts with GitLab tickets."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api",
            description="Authenticated with api scope",
            mandatory=True,
            alias="GitLab PAT with api scope",
        ),
    ]
    PROVIDER_TAGS = ["ticketing", "runbook"]
    PROVIDER_DISPLAY_NAME = "GitLab"

    def __init__(
            self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self._host = None
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validate that the provider has the required scopes.
        """

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}",
        }

        # first, validate user/api token are correct:
        resp = requests.get(
            f"{self.gitlab_host}/api/v4/personal_access_tokens/self",
            headers=headers,
            verify=False,
        )
        try:
            resp.raise_for_status()
            scopes = {
                "api": ("Missing api scope", True)['api' in resp.json()['scopes']]
            }
        except HTTPError as e:
            scopes = {
                "api": str(e)
            }
        return scopes

    def validate_config(self):
        self.authentication_config = GitlabProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def gitlab_host(self):
        # if not the first time, return the cached host
        if self._host:
            return self._host.rstrip("/")

        # if the user explicitly supplied a host with http/https, use it
        if self.authentication_config.host.startswith(
                "http://"
        ) or self.authentication_config.host.startswith("https://"):
            self._host = self.authentication_config.host
            return self.authentication_config.host.rstrip("/")

        # otherwise, try to use https:
        try:
            requests.get(
                f"https://{self.authentication_config.host}",
                verify=False,
            )
            self.logger.debug("Using https")
            self._host = f"https://{self.authentication_config.host}"
            return self._host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using http")
            self._host = f"http://{self.authentication_config.host}"
            return self._host.rstrip("/")
        # should happen only if the user supplied invalid host, so just let validate_config fail
        except Exception:
            return self.authentication_config.host.rstrip("/")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __get_auth_header(self):
        """
        Helper method to build the auth payload for gitlab api requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}"
        }

    # @staticmethod
    def __build_params_from_kwargs(self, kwargs: dict):
        params = dict()
        for param in kwargs:
            if isinstance(kwargs[param], list):
                params[param] = ",".join(kwargs[param])
            else:
                params[param] = kwargs[param]
        return params

    def get_gitlab_user_id(self):
        """
        Retrieve the user ID from the access token in GitLab.
        """
        url = f"{self.gitlab_host}/api/v4/user"
        headers = self.__get_auth_header()
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            user_data = response.json()
            print(user_data)
            return user_data['id']  # The user ID
        else:
            raise Exception(f"Failed to retrieve user info: {response.status_code}, {response.text}")
        
    def _format_repos(self, repos, project_id=None):
       """
       Format the repository data into a list of dictionaries.
       """
       if project_id is not None:
           if repos is not None:
               return {
                   "id": repos.get("id"),
                   "name": repos.get("name"),
                   "full_name": repos.get("full_name"),
                   "url": repos.get("web_url"),
                   "description": repos.get("description"),
                   "private": repos.get("visibility"),
                   "option_value": repos.get("id"),
                   "display_name": repos.get("path_with_namespace"),
                   "default_branch": repos.get("default_branch"),
               }
           return {}

       formatted_repos = []
       for repo in repos:
           formatted_repos.append(
               {
                   "id": repo.get("id"),
                   "name": repo.get("name"),
                   "full_name": repo.get("full_name"),
                   "url": repo.get("web_url"),
                   "description": repo.get("description"),
                   "private": repo.get("visibility"),
                   "option_value": repo.get("id"),
                   "display_name": repo.get("path_with_namespace"),
                   "default_branch": repo.get("default_branch"),
               }
           )

       return formatted_repos

    def pull_repositories(self, project_id=None):
       """Get user repositories."""
       if self.authentication_config.personal_access_token:
           user_id = self.get_gitlab_user_id()
           url = f"{self.gitlab_host}/api/v4/projects/{project_id}" if project_id else f"{self.gitlab_host}/api/v4/users/{user_id}/projects"
           resp = requests.get(
               url,
               headers=self.__get_auth_header()
           )
           try:
               resp.raise_for_status()
           except HTTPError as e:
               raise Exception(f"Failed to query repositories: {e}")

           repos = resp.json()
           return self._format_repos(repos, project_id)

       raise Exception("Failed to get repositories: personal_access_token not set")

    def _format_content(self, runbookContent, repo):
        """
        Format the content data into a dictionary.
        """
        return {
            "content": runbookContent.get("content"),
            "link": f"{self.gitlab_host}/api/v4/projects/{repo.get('id')}/repository/files/{runbookContent.get('file_path')}/raw",
            "encoding": runbookContent.get("encoding"),
            "file_name": runbookContent.get("file_name"),
        }


    def _format_runbook(self, runbook, repo, title, md_path):
        """
        Format the runbook data into a dictionary.
        """
        if runbook is None:
            raise Exception("Got empty runbook. Please check the runbook path and try again.")

        # Check if runbook is a list, if not convert to list
        if isinstance(runbook, list):
            runbook_contents = runbook      
        else:
            runbook_contents = [runbook] 

        # Filter runbook contents where type is "file"
        filtered_runbook_contents = [runbookContent for runbookContent in runbook_contents if runbookContent.get("type") == "file"]

        # Format the contents using a helper function
        contents = [self._format_content(runbookContent, repo) for runbookContent in filtered_runbook_contents]

        # Return formatted runbook data as dictionary
        return {
            "relative_path": md_path,
            "repo_id": repo.get("id"),
            "repo_name": repo.get("name"),
            "repo_display_name": repo.get("display_name"),
            "provider_type": "gitlab",  # This was changed from "github" to "gitlab", assuming it is intentional
            "provider_id": self.provider_id,  # Assuming this is supposed to be 'provider_id', not 'config'
            "contents": contents,
            "title": title,
        }
     

    def pull_runbook(self, repo=None, branch=None, md_path=None, title=None):
        """Retrieve markdown files from the GitLab repository."""
        repo = repo if repo else self.authentication_config.repository
        branch = branch if branch else "main"
        md_path = md_path if md_path else self.authentication_config.md_path

        repo_meta = self.pull_repositories(project_id=repo)

        if repo_meta and branch and md_path:
            repo_id = repo_meta.get("id")
            resp = requests.get(
                f"{self.gitlab_host}/api/v4/projects/{repo_id}/repository/files/{md_path}?ref={branch}",
                headers=self.__get_auth_header()
            )

            try:
                resp.raise_for_status()
            except HTTPError as e:
                raise Exception(f"Failed to get runbook: {e}")

            return self._format_runbook(resp.json(), repo_meta, title, md_path)

        raise Exception("Failed to get runbook: repository or md_path not set")       


    def _notify(self, id: str, title: str, description: str = "", labels: str = "", issue_type: str = "issue",
                **kwargs: dict):
        id = urllib.parse.quote(id, safe='')
        print(id)
        params = self.__build_params_from_kwargs(
            kwargs={**kwargs, 'title': title, 'description': description, 'labels': labels, 'issue_type': issue_type})
        print(self.gitlab_host)
        resp = requests.post(f"{self.gitlab_host}/api/v4/projects/{id}/issues", headers=self.__get_auth_header(),
                             params=params)
        try:
            resp.raise_for_status()
        except HTTPError as e:
            raise Exception(f"Failed to create issue: {str(e)}")
        return resp.json()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    gitlab_pat = os.environ.get("GITLAB_PAT")
    gitlab_host = os.environ.get("GITLAB_HOST")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="GitLab Provider",
        authentication={
            "personal_access_token": gitlab_pat,
            "host": gitlab_host,
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "md_path": os.environ.get("MARKDOWN_PATH")
        },
    )
    provider = GitlabProvider(context_manager, provider_id="gitlab", config=config)
    scopes = provider.validate_scopes()
    # Create ticket
    provider.notify(
        board_name="KEEP board",
        issue_type="Task",
        summary="Test Alert",
        description="Test Alert Description",
    )

    result = provider.pull_runbook(title="test")
    result = provider.pull_repositories()
    print(result)
