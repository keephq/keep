"""
NtfyProvider is a class that provides a way to send notifications to the user.
"""

import dataclasses

import pydantic
import requests
from urllib.parse import urljoin

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

    def __get_auth_headers(self):
        return {
            "Authorization": f"Bearer {self.authentication_config.access_token}"
        }

    def __send_alert(self, message=""):
        self.logger.debug(f"Sending notification to {self.authentication_config.subcription_topic}")

        NTFY_SUBSCRIPTION_TOPIC = self.authentication_config.subcription_topic
        NTFY_URL = urljoin(base="https://ntfy.sh/", url=NTFY_SUBSCRIPTION_TOPIC)

        try:
            response = requests.post(NTFY_URL, headers=self.__get_auth_headers(), data=message)

            if response.status_code == 401:
                raise ProviderException(
                    f"Failed to send notification to {NTFY_URL}. Error: Unauthorized"
                )
            
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            raise ProviderException(
                f"Failed to send notification to {NTFY_URL}. Error: {e}"
            )

    def _notify(self, message=""):
        return self.__send_alert(message)

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
        description="Ntfy Provider",
        authentication={
            "access_token": ntfy_access_token,
            "subcription_topic": ntfy_subscription_topic,
        },
    )

    provider = NtfyProvider(
        context_manager,
        provider_id="ntfy-keephq",
        config=config,
    )

    provider.notify(message="Test message from Keephq")