"""
GithubProvider is a provider that interacts with GitHub.
"""

import pydantic
from github import Github

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GithubProviderAuthConfig:
    """
    GithubProviderAuthConfig is a class that represents the authentication configuration for the GithubProvider.
    """

    access_token: str | None = None


class GithubProvider(BaseProvider):
    """
    GithubProvider is a class that provides a way to read data from AWS Cloudwatch.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
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


class GithubStarsProvider(GithubProvider):
    """
    GithubStarsProvider is a class that provides a way to read stars from a GitHub repository.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def query(
        self, repository: str, previous_stars_count: int = 0, **kwargs: dict
    ) -> dict:
        repo = self.client.get_repo(repository)
        stars_count = repo.stargazers_count
        new_stargazers = []

        if not previous_stars_count:
            previous_stars_count = 0

        if previous_stars_count and int(previous_stars_count) > 0:
            self.logger.debug(f"Getting new stargazers since {previous_stars_count}")
            stargazers_with_dates = [s for s in repo.get_stargazers_with_dates()][
                int(previous_stars_count) :
            ]
            for stargazer in stargazers_with_dates:
                new_stargazers.append(
                    {
                        "username": stargazer.user.login,
                        "starred_at": str(stargazer.starred_at),
                    }
                )
                self.logger.debug(f"New stargazer: {stargazer.user.login}")
        self.logger.debug(
            "Github stars output",
            extra={
                "stars": stars_count,
                "new_stargazers": new_stargazers,
                "new_stargazers_count": len(new_stargazers),
            },
        )
        return {
            "stars": stars_count,
            "new_stargazers": new_stargazers,
            "new_stargazers_count": len(new_stargazers),
        }


if __name__ == "__main__":
    github_stars_provider = GithubStarsProvider("test", ProviderConfig({}))
    result = github_stars_provider.query("keephq/keep", 910)
    print(result)
