"""
GithubProvider is a provider that interacts with GitHub.
"""

import dataclasses

import pydantic
from github import Github, GithubException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseRunBookProvider
from keep.providers.models.provider_config import ProviderConfig


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

class GithubProvider(BaseRunBookProvider):
    """
    Enrich alerts with data from GitHub.
    """

    PROVIDER_DISPLAY_NAME = "GitHub"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.client = self.__generate_client()

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


    def _format_repo(self, repo:dict):
        """
        Format the repository data.
        """
        if repo is not None:
                return {
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "url": repo.html_url,
                    "description": repo.description,
                    "private": repo.private,
                    "option_value": repo.name,
                    "display_name": repo.full_name,
                    "default_branch": repo.default_branch,
                }

        return {}    

    def _format_repos(self, repos:list[dict]):
        """
        Format the repository data into a list of dictionaries.
        """
        formatted_repos = []
        for repo in repos:
            formatted_repos.append(
                self._format_repo(repo)
            )

        return formatted_repos        

    def pull_repositories(self, project_id=None):
        """
        Get user repositories.
        """
        if self.authentication_config.access_token:
            client = Github(self.authentication_config.access_token)
        else:
            client = Github()
        user = client.get_user()
        repos = user.get_repos()
        if project_id:
            repo = client.get_repo(project_id)
            return self._format_repo(repo)
            
        repos_list = self._format_repos(repos)
        return repos_list


    def _format_content(self, runbookContent, repo):
        """
        Format the content data into a dictionary.
        """
        return {
            "content": runbookContent.content,
            "link": f"https://api.github.com/{repo.get('full_name')}/blob/{repo.get('default_branch')}/{runbookContent.path}",
            "encoding": runbookContent.encoding,
            "file_name": runbookContent.name
        }    

    def _format_runbook(self, runbook, repo, title, md_path):
        """
        Format the runbook data into a dictionary.
        """
        self.logger.info("runbook: %s", runbook)

        if runbook is None:
            raise Exception("Got empty runbook. Please check the runbook path and try again.")

        # Check if the runbook is a list, then set runbook_contents accordingly
        if isinstance(runbook, list):
            runbook_contents = runbook           
        else:
            runbook_contents = [runbook] 

        # Filter contents where type is "file"
        filtered_runbook_contents = [runbookContent for runbookContent in runbook_contents if runbookContent.type == "file"]

        # Format the contents using a helper function
        contents = [self._format_content(runbookContent, repo) for runbookContent in filtered_runbook_contents]

        # Return the formatted runbook data as a dictionary
        return {
            "relative_path": md_path,
            "repo_id": repo.get("id"),
            "repo_name": repo.get("name"),
            "repo_display_name": repo.get("display_name"),
            "provider_type": "github",
            "provider_id": self.provider_id,
            "contents": contents,
            "title": title,
        }


        

    def pull_runbook(self, repo=None, branch=None, md_path=None, title=None): 
        """Retrieve markdown files from the GitHub repository using the GitHub client."""

        repo_name = repo if repo else self.authentication_config.repository
        branch = branch  if branch else "main"
        md_path = md_path if  md_path else self.authentication_config.md_path  

    
        if repo_name and branch and md_path:
            # Initialize the GitHub client
            client =  self.__generate_client()

            try:
                # Get the repository
                user = client.get_user()
                username = user.login
                repo = client.get_repo(f"{username}/{repo_name}")
                if repo is None:
                    raise Exception(f"Repository {repo_name} not found")

                runbook = repo.get_contents(md_path, branch)
                response = self._format_runbook(runbook, self._format_repo(repo), title, md_path)
                return response

            except GithubException as e:
                raise Exception(f"Failed to retrieve runbook: {e}")

        raise Exception("Failed to get runbook: repository, branch, md_path, or access_token not set")        

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
            stargazers_with_dates[-1].user.login
            if len(stargazers_with_dates) > 1
            else ""
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
    github_pat = os.environ.get("GITHUB_PAT")

    github_stars_provider = GithubStarsProvider(
        context_manager,
        "test",
        ProviderConfig(authentication={
        "access_token": github_pat,
        }
        ),
    )

    result = github_stars_provider.query(
        repository="keephq/keep", previous_stars_count=910
    )
    print(result)


    # Initalize the provider and provider config
    config = ProviderConfig(
        description="GitHub Provider",
        authentication={
            "access_token": github_pat,
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "md_path": os.environ.get("MARKDOWN_PATH"),
        },
    )
    provider = GithubProvider(context_manager, provider_id="github", config=config)
    result = provider.pull_runbook(title="test")
    result = provider.pull_repositories()

    print(result)
