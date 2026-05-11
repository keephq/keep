"""
Rocket.Chat Provider is a class that implements the BaseOutputProvider interface for Rocket.Chat messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RocketchatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Personal Access Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )
    user_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat User ID",
            "config_main_group": "authentication",
        }
    )


@pydantic.dataclasses.dataclass
class RocketchatProviderPayload:
    """Rocket.Chat message payload configuration."""

    base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat server base URL (e.g., https://chat.example.com)",
            "config_main_group": "payload",
        }
    )


class RocketchatProvider(BaseProvider):
    """Send alert message to Rocket.Chat."""

    PROVIDER_DISPLAY_NAME = "Rocket.Chat"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RocketchatProviderAuthConfig(
            **self.config.authentication
        )
        self.payload_config = RocketchatProviderPayload(
            **self.config.payload
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the access token and user ID are valid by making a test request.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        room: str = None,
        alias: str = None,
        emoji: str = None,
        avatar: str = None,
    ):
        """
        Send a message to Rocket.Chat.
        https://developer.rocket.chat/docs/api/rest-api/methods/chat/postmessage
        """
        access_token = self.authentication_config.access_token
        user_id = self.authentication_config.user_id
        base_url = self.payload_config.base_url.rstrip("/")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        if not room:
            raise ProviderException(
                f"{self.__class__.__name__} room is required"
            )

        headers = {
            "X-Auth-Token": access_token,
            "X-User-Id": user_id,
            "Content-Type": "application/json",
        }

        payload = {"text": message}

        if room.startswith("#"):
            payload["channel"] = room
        elif room.startswith("@"):
            payload["roomId"] = room
        else:
            payload["roomId"] = room

        if alias:
            payload["alias"] = alias
        if emoji:
            payload["emoji"] = emoji
        if avatar:
            payload["avatar"] = avatar

        response = requests.post(
            f"{base_url}/api/v1/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid access token or user ID"
            )
        elif response.status_code == 400:
            raise ProviderException(
                f"{self.__class__.__name__} bad request - {response.text}"
            )
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: {response.status_code} - {response.text}"
            )

    def _notify(
        self,
        message: str = "",
        room: str = None,
        alias: str = None,
        emoji: str = None,
        avatar: str = None,
        **kwargs: dict,
    ):
        """
        Notify alert message to Rocket.Chat.

        Args:
            message (str): The message text to send.
            room (str): The room ID, channel name (with #), or user DM (with @).
            alias (str): The name to display as the sender.
            emoji (str): An emoji to display as the sender avatar.
            avatar (str): A URL to display as the sender avatar.
        """
        self.logger.debug("Notifying alert message to Rocket.Chat")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        if not room:
            raise ProviderException(
                f"{self.__class__.__name__} room is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            room=room,
            alias=alias,
            emoji=emoji,
            avatar=avatar,
        )

        self.logger.debug("Alert message notified to Rocket.Chat")
        return {"message": message, "room": room, "status": result.get("success"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    rocketchat_access_token = os.environ.get("ROCKETCHAT_ACCESS_TOKEN")
    rocketchat_user_id = os.environ.get("ROCKETCHAT_USER_ID")
    rocketchat_base_url = os.environ.get("ROCKETCHAT_BASE_URL")

    if rocketchat_access_token is None or rocketchat_user_id is None or rocketchat_base_url is None:
        raise Exception("ROCKETCHAT_ACCESS_TOKEN, ROCKETCHAT_USER_ID, and ROCKETCHAT_BASE_URL are required")

    config = ProviderConfig(
        description="Rocket.Chat Output Provider",
        authentication={
            "access_token": rocketchat_access_token,
            "user_id": rocketchat_user_id,
        },
        payload={"base_url": rocketchat_base_url},
    )
    provider = RocketchatProvider(
        context_manager, provider_id="rocketchat-test", config=config
    )

    provider.notify(message="Hello from Keep!", room="#general")
