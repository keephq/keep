"""
GithubProvider is a provider that interacts with GitHub.
"""

import dataclasses

import pydantic
from github import Github

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
        repo = self.client.get_repo(repository)
        commits = repo.get_commits()
        return commits[:n]

    def get_last_releases(self, repository: str, n: int = 10):
        repo = self.client.get_repo(repository)
        releases = repo.get_releases()
        return releases[:n]

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

    result = github_provider.get_
    print(result)
