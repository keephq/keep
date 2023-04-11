"""
TrelloOutput is a class that implements the BaseOutputProvider interface for Trello updates.
"""
import dataclasses

import pydantic
import requests
import json

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TrelloProviderAuthConfig:
    """Trello authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Trello API Key"}
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Trello API Token"}
    )


class TrelloProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.authentication_config = TrelloProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def query(self, **kwargs: dict):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Fetching data from Trello")
        trello_api_key = self.authentication_config.api_key
        trello_api_token = self.authentication_config.api_token
        
        board_id = kwargs.pop("board_id", "")
        filter = kwargs.pop("filter", "[]")

        request_url = 'https://api.trello.com/1/boards/{board_id}/actions?key={trello_api_key}&token={trello_api_token}&filter={filter}'.format(board_id=board_id, trello_api_key=trello_api_key, trello_api_token=trello_api_token, filter=filter)
        response = requests.get(
            request_url
        )
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Trello: {response.text}"
            )

        print(json.dumps(response.json(), indent=2))
        self.logger.debug("Fetched data from Trello")
        cards = response.json()
        return {
            "cards": cards,
            "number_of_cards": len(cards)
        }


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    trello_api_key = os.environ.get("TRELLO_API_KEY")
    trello_api_token = os.environ.get("TRELLO_API_TOKEN")

    print(trello_api_key)
    print(trello_api_token)

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Trello Input Provider",
        authentication={"api_key": trello_api_key, "api_token": trello_api_token},
    )
    provider = TrelloProvider(provider_id="trello-test", config=config)
    provider.query(
        board_id="HuwkA0Dd",
        filter="createCard"
    )
