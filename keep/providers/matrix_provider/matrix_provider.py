"""
Matrix Provider is a class that implements the BaseOutputProvider interface for Matrix (Element) messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MatrixProviderAuthConfig:
    """Matrix authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix Access Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )
    homeserver_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix Homeserver URL (e.g. https://matrix.org)",
            "config_main_group": "authentication",
        }
    )
    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix Room ID (e.g. !roomid:matrix.org)",
            "config_main_group": "authentication",
        }
    )


class MatrixProvider(BaseProvider):
    """Send alert message to Matrix."""

    PROVIDER_DISPLAY_NAME = "Matrix"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MatrixProviderAuthConfig(
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
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(self, message: str, formatted_message: str = None):
        """
        Send a message to Matrix.
        https://spec.matrix.org/v1.12/client-server-api/#put_matrixclientv3roomsroomidsendeventtypetxnid
        """
        access_token = self.authentication_config.access_token
        homeserver_url = self.authentication_config.homeserver_url.rstrip("/")
        room_id = self.authentication_config.room_id

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "msgtype": "m.text",
            "body": message,
        }

        if formatted_message:
            payload["formatted_body"] = formatted_message
            payload["format"] = "org.matrix.custom.html"

        response = requests.post(
            f"{homeserver_url}/_matrix/client/r0/rooms/{room_id}/send/m.room.message",
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
        formatted_message: str = None,
        **kwargs: dict,
    ):
        """
        Notify alert message to Matrix.

        Args:
            message (str): The plain text message to send.
            formatted_message (str): Optional HTML formatted message.
        """
        self.logger.debug("Notifying alert message to Matrix")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            formatted_message=formatted_message,
        )

        self.logger.debug("Alert message notified to Matrix")
        return {"message": message, "event_id": result.get("event_id"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    matrix_access_token = os.environ.get("MATRIX_ACCESS_TOKEN")
    matrix_homeserver_url = os.environ.get("MATRIX_HOMESERVER_URL")
    matrix_room_id = os.environ.get("MATRIX_ROOM_ID")

    if matrix_access_token is None or matrix_homeserver_url is None or matrix_room_id is None:
        raise Exception("MATRIX_ACCESS_TOKEN, MATRIX_HOMESERVER_URL and MATRIX_ROOM_ID are required")

    config = ProviderConfig(
        description="Matrix Output Provider",
        authentication={
            "access_token": matrix_access_token,
            "homeserver_url": matrix_homeserver_url,
            "room_id": matrix_room_id,
        },
    )
    provider = MatrixProvider(
        context_manager, provider_id="matrix-test", config=config
    )

    provider.notify(message="Hello from Keep!")
