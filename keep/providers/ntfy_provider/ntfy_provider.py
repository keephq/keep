"""
NtfyProvider is a class that provides a way to send notifications to the user.
"""

import base64
import dataclasses
from urllib.parse import urljoin

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
            "required": False,
            "description": "Ntfy Access Token",
            "sensitive": True,
        },
        default=None,
    )

    host: pydantic.AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Ntfy Host URL (For self-hosted Ntfy only)",
            "sensitive": False,
            "hint": "http://localhost:80",
            "validation": "any_http_url",
        },
        default=None,
    )

    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Ntfy Username (For self-hosted Ntfy only)",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Ntfy Password (For self-hosted Ntfy only)",
            "sensitive": True,
        },
        default=None,
    )


class NtfyProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Ntfy.sh"
    PROVIDER_CATEGORY = ["Collaboration"]

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
        if (
            self.authentication_config.access_token is None
            and self.authentication_config.host is None
        ):
            raise ProviderException("Either Access Token or Host is required")
        if self.authentication_config.host is not None:
            if self.authentication_config.username is None:
                raise ProviderException("Username is required when host is provided")
            if self.authentication_config.password is None:
                raise ProviderException("Password is required when host is provided")

    def __get_auth_headers(self):
        if self.authentication_config.access_token is not None:
            return {
                "Authorization": f"Bearer {self.authentication_config.access_token}"
            }

        else:
            username = self.authentication_config.username
            password = self.authentication_config.password
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode(
                "utf-8"
            )

            return {"Authorization": f"Basic {token}"}

    def __send_alert(self, message="", topic=None):
        self.logger.debug(f"Sending notification to {topic}")

        if self.authentication_config.host is not None:
            base_url = self.authentication_config.host
            if not base_url.endswith("/"):
                base_url += "/"
            NTFY_URL = urljoin(base=base_url, url=topic)
        else:
            NTFY_URL = urljoin(base="https://ntfy.sh/", url=topic)

        try:
            response = requests.post(
                NTFY_URL, headers=self.__get_auth_headers(), data=message
            )

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

    def _notify(self, message="", topic=None, **kwargs):
        if not message or not topic:
            raise ProviderException(
                "Message and Topic are required to send notification"
            )
        return self.__send_alert(message, topic, **kwargs)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    ntfy_access_token = os.environ.get("NTFY_ACCESS_TOKEN")
    ntfy_host = os.environ.get("NTFY_HOST")
    ntfy_username = os.environ.get("NTFY_USERNAME")
    ntfy_password = os.environ.get("NTFY_PASSWORD")
    ntfy_subscription_topic = os.environ.get("NTFY_SUBSCRIPTION_TOPIC")

    if ntfy_access_token is None and ntfy_host is None:
        raise Exception("NTFY_ACCESS_TOKEN or NTFY_HOST is required")

    if ntfy_host is not None:
        if ntfy_username is None:
            raise Exception("NTFY_USERNAME is required")
        if ntfy_password is None:
            raise Exception("NTFY_PASSWORD is required")

    if ntfy_access_token is not None:
        config = ProviderConfig(
            description="Ntfy Provider",
            authentication={
                "access_token": ntfy_access_token,
                "subcription_topic": ntfy_subscription_topic,
            },
        )

    else:
        config = ProviderConfig(
            description="Ntfy Provider",
            authentication={
                "host": ntfy_host,
                "username": ntfy_username,
                "password": ntfy_password,
                "subcription_topic": ntfy_subscription_topic,
            },
        )

    provider = NtfyProvider(
        context_manager,
        provider_id="ntfy-keephq",
        config=config,
    )

    provider.notify(message="Test message from Keephq")
