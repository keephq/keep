"""
JiraProvider is a class that implements the BaseProvider interface for Jira updates.
"""
import dataclasses

import pydantic
import requests

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class JiraProviderAuthConfig:
    """Jira authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlassian Jira API Token",
            "sensitive": True,
        }
    )


class JiraProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.authentication_config = JiraProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def query(self, **kwargs: dict):
        """
        API for fetching issues:
        https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-issue-get

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Fetching data from Jira")

        jira_api_token = self.authentication_config.api_token

        host = kwargs.pop("host", "")
        board_id = kwargs.pop("board_id", "")
        email = kwargs.pop("email", "")

        request_url = f"https://{host}/rest/agile/1.0/board/{board_id}/issue"
        response = requests.get(request_url, auth=(email, jira_api_token))
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Jira: {response.text}"
            )
        self.logger.debug("Fetched data from Jira")

        issues = response.json()
        return {"number_of_issues": issues["total"]}


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    jira_api_token = os.environ.get("JIRA_API_TOKEN")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Jira Input Provider",
        authentication={"api_token": jira_api_token},
    )
    provider = JiraProvider(provider_id="jira", config=config)
    provider.query(host="JIRA HOST", board_id="1", email="YOUR EMAIL")
