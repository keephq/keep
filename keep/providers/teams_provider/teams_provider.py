"""
TeamsProvider is a class that implements the BaseOutputProvider interface for Microsoft Teams messages.
"""

import dataclasses

import json5 as json
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
            "validation": "https_url",
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
        typeCard="message",
        themeColor=None,
        sections=[],
        schema="http://adaptivecards.io/schemas/adaptive-card.json",
        attachments=[],
        **kwargs: dict,
    ):
        """
        Notify alert message to Teams using the Teams Incoming Webhook API

        Args:
            message (str): The message to send
            typeCard (str): Type of card to send ("MessageCard" or "message" for Adaptive Cards)
            themeColor (str): Color theme for MessageCard
            sections (list): Sections for MessageCard or Adaptive Card content
            attachments (list): Attachments for Adaptive Card
            **kwargs (dict): Additional arguments
        """
        self.logger.debug("Notifying alert message to Teams")
        webhook_url = self.authentication_config.webhook_url

        if sections and isinstance(sections, str):
            try:
                sections = json.loads(sections)
            except Exception as e:
                self.logger.error(f"Failed to decode sections string to JSON: {e}")

        if attachments and isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except Exception as e:
                self.logger.error(f"Failed to decode attachments string to JSON: {e}")

        if typeCard == "message":
            # Adaptive Card format
            payload = {"type": "message"}
            if attachments:
                payload["attachments"] = attachments
            else:
                payload["attachments"] = (
                    [
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "contentUrl": None,
                            "content": {
                                "$schema": schema,
                                "type": "AdaptiveCard",
                                "version": "1.2",
                                "body": (
                                    sections
                                    if sections
                                    else [{"type": "TextBlock", "text": message}]
                                ),
                            },
                        }
                    ],
                )
        else:
            # Standard MessageCard format
            payload = {
                "@type": typeCard,
                "themeColor": themeColor,
                "text": message,
                "sections": sections,
            }

        response = requests.post(webhook_url, json=payload)
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Teams: {response.text}"
            )

        self.logger.debug("Alert message notified to Teams")
        return response.json()


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
        typeCard="message",
        sections=[
            {"type": "TextBlock", "text": "Danilo Vaz"},
            {"type": "TextBlock", "text": "Tal from Keep"},
        ],
    )
