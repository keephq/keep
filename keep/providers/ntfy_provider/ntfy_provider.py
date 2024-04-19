"""
NtfyProvider is a class that provides a way to send notifications to the user.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NtfyProviderAuthConfig:
    """
    NtfyProviderAuthConfig is a class that holds the authentication information for the NtfyProvider.
    """

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Ntfy Access Token",
            "sensitive": True,
        },
    )

    subcription_topic: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Ntfy Subcription Topic",
            "sensitive": False,
        },
    )


class NtfyProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Ntfy.sh"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_alert",
            mandatory=True,
            alias="Send Alert",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        validated_scopes["send_alert"] = True
        return validated_scopes

    def validate_config(self):
        self.authentication_config = NtfyProviderAuthConfig(
            **self.config.authentication
        )

    def _notify(self, **kwargs: dict):
        self.logger.debug(
            f"Sending notification to {self.authentication_config.subcription_topic}"
        )

        message = kwargs.get("message")

        NTFY_ACCESS_TOKEN = self.authentication_config.access_token
        NTFY_SUBSCRIPTION_TOPIC = self.authentication_config.subcription_topic
        NTFY_URL = "https://ntfy.sh/" + NTFY_SUBSCRIPTION_TOPIC

        headers = {"Authorization": f"Bearer {NTFY_ACCESS_TOKEN}"}

        try:
            response = requests.post(NTFY_URL, headers=headers, data=message)

            if response.status_code != 200:
                raise ProviderException(
                    f"Failed to send notification to {NTFY_URL}. Response: {response.text}"
                )

        except Exception as e:
            raise ProviderException(
                f"Failed to send notification to {NTFY_URL}. Error: {e}"
            )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    ntfy_access_token = os.environ.get("NTFY_ACCESS_TOKEN")
    ntfy_subscription_topic = os.environ.get("NTFY_SUBSCRIPTION_TOPIC")

    config = ProviderConfig(
        description="Ntfy Input Provider",
        authentication={
            "access_token": ntfy_access_token,
            "subcription_topic": ntfy_subscription_topic,
        },
    )
    provider = NtfyProvider(context_manager, provider_id="ntfy", config=config)
    provider.validate_scopes()
    provider.notify(message="Keep Alert")
