"""
VonageProvider is a class that implements the BaseProvider interface for Vonage SMS.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class VonageProviderAuthConfig:
    """Vonage authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Vonage API Key",
            "sensitive": False,
            "documentation_url": "https://developer.vonage.com/en/account/secret-management",
        }
    )

    api_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Vonage API Secret",
            "sensitive": True,
            "documentation_url": "https://developer.vonage.com/en/account/secret-management",
        }
    )

    from_number: str = dataclasses.field(
        default="Keep",
        metadata={
            "required": False,
            "description": "Sender ID or phone number (default: Keep)",
            "sensitive": False,
        },
    )

    to_number: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Recipient phone number in E.164 format (e.g. 15551234567)",
            "sensitive": False,
        }
    )


class VonageProvider(BaseProvider):
    """Send SMS alerts via Vonage (Nexmo) API."""

    PROVIDER_DISPLAY_NAME = "Vonage SMS"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_sms",
            description="The API key/secret have permission to send SMS",
            mandatory=True,
            alias="Send SMS",
        )
    ]

    VONAGE_SMS_URL = "https://rest.nexmo.com/sms/json"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VonageProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes: dict[str, bool | str] = {}
        try:
            response = requests.post(
                self.VONAGE_SMS_URL,
                json={
                    "from": self.authentication_config.from_number,
                    "to": self.authentication_config.to_number,
                    "text": "Keep scope validation",
                    "api_key": self.authentication_config.api_key,
                    "api_secret": self.authentication_config.api_secret,
                },
                timeout=10,
            )
            data = response.json()
            messages = data.get("messages", [{}])
            status = messages[0].get("status", "-1")
            if str(status) == "0":
                validated_scopes["send_sms"] = True
            else:
                error_text = messages[0].get("error-text", "Unknown error")
                validated_scopes["send_sms"] = error_text
        except Exception as e:
            validated_scopes["send_sms"] = str(e)
        return validated_scopes

    def dispose(self):
        pass

    def _notify(self, message: str = "", to_number: str = "", **kwargs: dict):
        """
        Send an SMS via Vonage REST API.

        Args:
            message (str): SMS text content.
            to_number (str): Override recipient number; falls back to auth config.
        """
        self.logger.debug("Sending SMS via Vonage")

        recipient = to_number or self.authentication_config.to_number
        if not recipient:
            raise ProviderException(
                f"{self.__class__.__name__}: to_number is required"
            )

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__}: message is required"
            )

        payload = {
            "from": self.authentication_config.from_number,
            "to": recipient,
            "text": message,
            "api_key": self.authentication_config.api_key,
            "api_secret": self.authentication_config.api_secret,
        }

        try:
            response = requests.post(self.VONAGE_SMS_URL, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            messages = data.get("messages", [{}])
            status = messages[0].get("status", "-1")
            if str(status) != "0":
                error_text = messages[0].get("error-text", "Unknown error")
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send SMS: {error_text}"
                )
        except ProviderException:
            raise
        except Exception as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send SMS via Vonage: {e}"
            )

        self.logger.debug("SMS sent via Vonage")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Vonage SMS Provider",
        authentication={
            "api_key": os.environ.get("VONAGE_API_KEY"),
            "api_secret": os.environ.get("VONAGE_API_SECRET"),
            "from_number": os.environ.get("VONAGE_FROM_NUMBER", "Keep"),
            "to_number": os.environ.get("VONAGE_TO_NUMBER"),
        },
    )
    provider = VonageProvider(
        context_manager, provider_id="vonage-test", config=config
    )
    provider.notify(message="Keep Alert - test notification")
