"""
MatrixProvider implements the BaseOutputProvider interface for Matrix (Element) notifications.
"""
import dataclasses
import time

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MatrixProviderAuthConfig:
    homeserver_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix homeserver URL (e.g. https://matrix.org)",
        }
    )
    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix user access token",
            "sensitive": True,
        }
    )
    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix room ID (e.g. !abc123:matrix.org)",
        }
    )


class MatrixProvider(BaseProvider):
    """Send alert notifications to Matrix rooms via Client-Server API."""

    PROVIDER_DISPLAY_NAME = "Matrix"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MatrixProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: dict):
        """
        Send a message to a Matrix room via the Client-Server API.
        https://spec.matrix.org/v1.6/client-server-api/#sending-events

        Args:
            message (str): The message body to send to the room.
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message"
            )

        base = self.authentication_config.homeserver_url.rstrip("/")
        room = self.authentication_config.room_id
        txn_id = str(int(time.time() * 1000))
        url = f"{base}/_matrix/client/v3/rooms/{room}/send/m.room.message/{txn_id}"

        headers = {
            "Authorization": f"Bearer {self.authentication_config.access_token}"
        }
        payload = {"msgtype": "m.text", "body": message}

        response = requests.put(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed: HTTP {response.status_code} - {response.text}"
            )

        self.logger.debug("Matrix notification sent")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Matrix Output Provider",
        authentication={
            "homeserver_url": os.environ.get("MATRIX_HOMESERVER_URL"),
            "access_token": os.environ.get("MATRIX_ACCESS_TOKEN"),
            "room_id": os.environ.get("MATRIX_ROOM_ID"),
        },
    )
    provider = MatrixProvider(
        context_manager, provider_id="matrix-test", config=config
    )
    provider.notify(message="Test alert from Keep")
