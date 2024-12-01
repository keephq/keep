"""
Slack provider is an interface for Slack messages.
"""

import dataclasses
import json
import os

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SlackProviderAuthConfig:
    """Slack authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Slack Webhook Url",
            "sensitive": True,
        },
        default="",
    )
    access_token: str = dataclasses.field(
        metadata={
            "description": "For access token installation flow, use Keep UI",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default="",
    )


class SlackProvider(BaseProvider):
    """Send alert message to Slack."""

    PROVIDER_DISPLAY_NAME = "Slack"
    OAUTH2_URL = os.environ.get("SLACK_OAUTH2_URL")
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")
    SLACK_API = "https://slack.com/api"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SlackProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.webhook_url
            and not self.authentication_config.access_token
        ):
            raise Exception("Slack webhook url OR Slack access token is required")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def oauth2_logic(**payload) -> dict:
        """
        Logic for handling oauth2 callback.

        Args:
            payload (dict): The payload from the oauth2 callback.

        Returns:
            dict: The provider configuration.
        """
        code = payload.get("code")
        if not code:
            raise Exception("No code provided")
        exchange_request_payload = {
            **payload,
            "client_id": SlackProvider.SLACK_CLIENT_ID,
            "client_secret": SlackProvider.SLACK_CLIENT_SECRET,
        }
        response = requests.post(
            f"{SlackProvider.SLACK_API}/oauth.v2.access",
            data=exchange_request_payload,
        )
        response_json = response.json()
        if not response.ok or not response_json.get("ok"):
            raise Exception(
                response_json.get("error"),
            )
        new_provider_info = {"access_token": response_json.get("access_token")}

        team_name = response_json.get("team", {}).get("name")
        if team_name:
            new_provider_info["provider_name"] = team_name

        return new_provider_info

    def _notify(
        self,
        message="",
        blocks=[],
        channel="",
        slack_timestamp="",
        thread_timestamp="",
        attachments=[],
        username="",
        **kwargs: dict,
    ):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        notify_data = None
        self.logger.info(
            f"Notifying message to Slack using {'webhook' if self.authentication_config.webhook_url else 'access token'}",
            extra={
                "slack_message": message,
                "blocks": blocks,
                "channel": channel,
            },
        )
        if not message:
            if not blocks:
                raise ProviderException(
                    "Message is required - see for example https://github.com/keephq/keep/blob/main/examples/workflows/slack_basic.yml#L16"
                )
            message = blocks[0].get("text")
        payload = {
            "channel": channel,
            "text": message,
            "blocks": (
                json.dumps(blocks)
                if isinstance(blocks, dict) or isinstance(blocks, list)
                else blocks
            ),
        }
        if attachments:
            payload["attachments"] = (
                json.dumps(attachments)
                if isinstance(attachments, dict) or isinstance(attachments, list)
                else blocks
            )
        if username:
            payload["username"] = username

        if self.authentication_config.webhook_url:
            # If attachments are present, we need to send them as the payload with nothing else
            # Also, do not encode the payload as json, but as x-www-form-urlencoded
            # Only reference I found for it is: https://getkeep.slack.com/services/B082F60L9GX?added=1 and
            # https://stackoverflow.com/questions/42993602/slack-chat-postmessage-attachment-gives-no-text
            if payload["attachments"]:
                payload["attachments"] = attachments
                response = requests.post(
                    self.authentication_config.webhook_url,
                    data={"payload": json.dumps(payload)},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            else:
                response = requests.post(
                    self.authentication_config.webhook_url,
                    json=payload,
                )
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Slack: {response.text}"
                )
        elif self.authentication_config.access_token:
            if not channel:
                raise ProviderException("Channel is required (E.g. C12345)")
            payload["token"] = self.authentication_config.access_token
            if slack_timestamp == "" and thread_timestamp == "":
                self.logger.info("Sending a new message to Slack")
                method = "chat.postMessage"
            else:
                self.logger.info(f"Updating Slack message with ts: {slack_timestamp}")
                if slack_timestamp:
                    payload["ts"] = slack_timestamp
                    method = "chat.update"
                else:
                    method = "chat.postMessage"
                    payload["thread_ts"] = thread_timestamp

            response = requests.post(
                f"{SlackProvider.SLACK_API}/{method}", data=payload
            )

            response_json = response.json()
            if not response.ok or not response_json.get("ok"):
                raise ProviderException(
                    f"Failed to notify alert message to Slack: {response_json.get('error')}"
                )
            notify_data = {"slack_timestamp": response_json["ts"]}
        self.logger.info("Message notified to Slack")
        return notify_data


if __name__ == "__main__":
    # Output debug messages
    import logging

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    # Initalize the provider and provider config
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    access_token = os.environ.get("SLACK_ACCESS_TOKEN")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if access_token:
        config = {
            "authentication": {"access_token": access_token},
        }
    elif webhook_url:
        config = {
            "authentication": {"webhook_url": webhook_url},
        }
    # you need some creds
    else:
        raise Exception("please provide either access token or webhook url")

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="slack-keephq",
        provider_type="slack",
        provider_config=config,
    )
    provider.notify(
        message="Simple alert showing context with name: John Doe",
        channel="C04P7QSG692",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Danny Torrence left the following review for your property:",
                },
            },
            {
                "type": "section",
                "block_id": "section567",
                "text": {
                    "type": "mrkdwn",
                    "text": "<https://example.com|Overlook Hotel> \n :star: \n Doors had too many axe holes, guest in room 237 was far too rowdy, whole place felt stuck in the 1920s.",
                },
                "accessory": {
                    "type": "image",
                    "image_url": "https://is5-ssl.mzstatic.com/image/thumb/Purple3/v4/d3/72/5c/d3725c8f-c642-5d69-1904-aa36e4297885/source/256x256bb.jpg",
                    "alt_text": "Haunted hotel image",
                },
            },
            {
                "type": "section",
                "block_id": "section789",
                "fields": [{"type": "mrkdwn", "text": "*Average Rating*\n1.0"}],
            },
        ],
        attachments=[
            {
                "fallback": "Plain-text summary of the attachment.",
                "color": "#2eb886",
                "title": "Slack API Documentation",
                "title_link": "https://api.slack.com/",
                "text": "Optional text that appears within the attachment",
                "footer": "Slack API",
                "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
            }
        ],
    )
