"""
TeamsProvider is a class that implements the BaseOutputProvider interface for Microsoft Teams messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class TeamsProviderAuthConfig:
    """Teams authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Teams Webhook Url",
            "sensitive": True,
            "validation": "https_url"
        }
    )


class TeamsProvider(BaseProvider):
    """Send alert message to Teams."""

    PROVIDER_DISPLAY_NAME = "Microsoft Teams"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TeamsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        message="",
        typeCard="MessageCard",
        themeColor=None,
        sections=[],
        **kwargs: dict,
    ):
        """
        Notify alert message to Teams using the Teams Incoming Webhook API
        https://learn.microsoft.com/pt-br/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using?tabs=cURL

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Teams")

        webhook_url = self.authentication_config.webhook_url

        response = requests.post(
            webhook_url,
            json={
                "@type": typeCard,
                "themeColor": themeColor,
                "text": message,
                "sections": sections,
            },
        )
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Teams: {response.text}"
            )

        self.logger.debug("Alert message notified to Teams")


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

    teams_webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="teams-test",
        description="Teams Output Provider",
        authentication={"webhook_url": teams_webhook_url},
    )
    provider = TeamsProvider(context_manager, provider_id="teams", config=config)
    provider.notify(
        typeCard="MessageCard",
        themeColor="0076D7",
        message="Microsoft Teams alert",
        sections=[
            {"name": "Assigned to", "value": "Danilo Vaz"},
            {"name": "Sum", "value": 10},
            {"name": "Count", "value": 100},
        ],
    )
