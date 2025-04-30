"""
TeamsProvider is a class that implements the BaseOutputProvider interface for Microsoft Teams messages.
"""

import dataclasses
from typing import Any, Optional

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
        message: str = "",
        typeCard: str = "message",
        themeColor: Optional[str] = None,
        sections: str | list = [],
        schema: str = "http://adaptivecards.io/schemas/adaptive-card.json",
        attachments: str | list = [],
        mentions: str | list = [],
        **kwargs: dict[str, Any],
    ):
        """
        Notify alert message to Teams using the Teams Incoming Webhook API

        Args:
            message (str): The message to send
            typeCard (str): The card type. Can be "MessageCard" (legacy) or "message" (for Adaptive Cards). Default is "message"
            themeColor (str): Hexadecimal color (only used with MessageCard type)
            sections (str | list): For MessageCard: Array of custom information sections. For Adaptive Cards: Array of card elements following the Adaptive Card schema. Can be provided as a JSON string or array.
            attachments (str | list): Custom attachments array for Adaptive Cards (overrides default attachment structure). Can be provided as a JSON string or array.
            schema (str): Schema URL for Adaptive Cards. Default is "http://adaptivecards.io/schemas/adaptive-card.json"
            mentions (str | list): List of user mentions to include in the Adaptive Card. Each mention should be a dict with 'id' (user ID, Microsoft Entra Object ID, or UPN) and 'name' (display name) keys.
                Example: [{"id": "user-id-123", "name": "John Doe"}, {"id": "john.doe@example.com", "name": "John Doe"}]
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

        if mentions and isinstance(mentions, str):
            try:
                mentions = json.loads(mentions)
            except Exception as e:
                self.logger.error(f"Failed to decode mentions string to JSON: {e}")

        if typeCard == "message":
            # Adaptive Card format
            payload = {"type": "message"}

            # Process the card content
            card_content = {
                "$schema": schema,
                "type": "AdaptiveCard",
                "version": "1.2",
                "body": (
                    sections if sections else [{"type": "TextBlock", "text": message}]
                ),
            }

            # Add mentions if provided
            if mentions:
                entities = []
                for mention in mentions:
                    if (
                        not isinstance(mention, dict)
                        or "id" not in mention
                        or "name" not in mention
                    ):
                        self.logger.warning(
                            f"Invalid mention format: {mention}. Skipping."
                        )
                        continue

                    mention_text = f"<at>{mention['name']}</at>"
                    entities.append(
                        {
                            "type": "mention",
                            "text": mention_text,
                            "mentioned": {"id": mention["id"], "name": mention["name"]},
                        }
                    )

                if entities:
                    card_content["msteams"] = {"entities": entities}

            if attachments:
                payload["attachments"] = attachments
            else:
                payload["attachments"] = [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": card_content,
                    }
                ]
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
        return {"response_text": response.text}


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
            {
                "type": "TextBlock",
                "text": "Hello <at>Tal from Keep</at>, please review this alert!",
            },
        ],
        mentions=[{"id": "tal@example.com", "name": "Tal from Keep"}],
    )
