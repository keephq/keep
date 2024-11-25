"""
TrelloOutput is a class that implements the BaseOutputProvider interface for Trello updates.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TrelloProviderAuthConfig:
    """Trello authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Trello API Key", "sensitive": True}
    )
    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Trello API Token",
            "sensitive": True,
        }
    )


class TrelloProvider(BaseProvider):
    """Enrich alerts with data from Trello."""

    PROVIDER_DISPLAY_NAME = "Trello"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TrelloProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _query(self, board_id: str = "", filter: str = "createCard", **kwargs: dict):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Fetching data from Trello")

        trello_api_key = self.authentication_config.api_key
        trello_api_token = self.authentication_config.api_token

        request_url = f"https://api.trello.com/1/boards/{board_id}/actions?key={trello_api_key}&token={trello_api_token}&filter={filter}"
        response = requests.get(request_url)
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Trello: {response.text}"
            )
        self.logger.debug("Fetched data from Trello")

        cards = response.json()
        return {"cards": cards, "number_of_cards": len(cards)}


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

    trello_api_key = os.environ.get("TRELLO_API_KEY")
    trello_api_token = os.environ.get("TRELLO_API_TOKEN")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Trello Input Provider",
        authentication={"api_key": trello_api_key, "api_token": trello_api_token},
    )
    provider = TrelloProvider(context_manager, provider_id="trello-test", config=config)
    provider.query(board_id="trello-board-id", filter="createCard")
