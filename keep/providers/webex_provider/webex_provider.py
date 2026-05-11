"""
Cisco Webex Provider is a class that implements the BaseOutputProvider interface for Cisco Webex messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WebexProviderAuthConfig:
    """Cisco Webex authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Cisco Webex Bot Access Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class WebexProvider(BaseProvider):
    """Send alert message to Cisco Webex."""

    PROVIDER_DISPLAY_NAME = "Cisco Webex"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    WEBEX_API_URL = "https://webexapis.com/v1/messages"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WebexProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the access token is valid by making a test request.
        """
        try:
            self._send_message("Keep test message", roomId="test")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        roomId: str = None,
        toPersonEmail: str = None,
        toPersonId: str = None,
        markdown: str = None,
    ):
        """
        Send a message to Cisco Webex.
        https://developer.webex.com/docs/api/v1/messages/create-a-message
        """
        access_token = self.authentication_config.access_token

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        if not roomId and not toPersonEmail and not toPersonId:
            raise ProviderException(
                f"{self.__class__.__name__} roomId, toPersonEmail, or toPersonId is required"
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {}

        if roomId:
            payload["roomId"] = roomId
        if toPersonEmail:
            payload["toPersonEmail"] = toPersonEmail
        if toPersonId:
            payload["toPersonId"] = toPersonId
        if markdown:
            payload["markdown"] = markdown
        else:
            payload["text"] = message

        response = requests.post(
            self.WEBEX_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid access token"
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
        roomId: str = None,
        toPersonEmail: str = None,
        toPersonId: str = None,
        markdown: str = None,
        **kwargs: dict,
    ):
        """
        Notify alert message to Cisco Webex.

        Args:
            message (str): The message text to send.
            roomId (str): The Webex room ID to send the message to.
            toPersonEmail (str): The email address of the recipient.
            toPersonId (str): The Webex person ID of the recipient.
            markdown (str): Markdown-formatted message (overrides text if provided).
        """
        self.logger.debug("Notifying alert message to Cisco Webex")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            roomId=roomId,
            toPersonEmail=toPersonEmail,
            toPersonId=toPersonId,
            markdown=markdown,
        )

        self.logger.debug("Alert message notified to Cisco Webex")
        return {
            "message": message,
            "id": result.get("id"),
            "sent": True,
        }


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    webex_token = os.environ.get("WEBEX_ACCESS_TOKEN")
    webex_room_id = os.environ.get("WEBEX_ROOM_ID")

    if webex_token is None:
        raise Exception("WEBEX_ACCESS_TOKEN is required")

    config = ProviderConfig(
        description="Cisco Webex Output Provider",
        authentication={"access_token": webex_token},
    )
    provider = WebexProvider(
        context_manager, provider_id="webex-test", config=config
    )

    provider.notify(message="Hello from Keep!", roomId=webex_room_id)
