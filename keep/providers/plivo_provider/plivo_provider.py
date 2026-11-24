"""
PlivoProvider is a class that implements the BaseProvider interface for Plivo SMS.
"""

import dataclasses

import plivo
import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class PlivoProviderAuthConfig:
    """Plivo authentication configuration."""

    auth_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Plivo Auth ID",
            "sensitive": False,
            "documentation_url": "https://www.plivo.com/docs/messaging/quickstart/python/",
        }
    )

    auth_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Plivo Auth Token",
            "sensitive": True,
            "documentation_url": "https://www.plivo.com/docs/messaging/quickstart/python/",
        }
    )

    from_phone_number: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Plivo source number or sender ID",
            "sensitive": False,
            "documentation_url": "https://www.plivo.com/docs/messaging/concepts/sms/",
        }
    )


class PlivoProvider(BaseProvider):
    """Send SMS via Plivo."""

    PROVIDER_DISPLAY_NAME = "Plivo"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_sms",
            description="The credentials can send SMS via the Plivo Messages API",
            mandatory=True,
            alias="Send SMS",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self) -> dict[str, bool | str]:
        # A Plivo send is billed and not idempotent (unlike Twilio's magic test
        # number), so validate the credentials with a read instead of a test send.
        validated_scopes = {}
        try:
            client = plivo.RestClient(
                self.authentication_config.auth_id,
                self.authentication_config.auth_token,
            )
            client.messages.list(limit=1)
            validated_scopes["send_sms"] = True
        except Exception as e:
            self.logger.warning(
                "Failed to validate scope send_sms",
                extra={"reason": str(e)},
            )
            validated_scopes["send_sms"] = str(e)

        return validated_scopes

    def validate_config(self):
        self.authentication_config = PlivoProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self, message_body: str = "", to_phone_number: str = "", **kwargs: dict
    ):
        """
        Send an SMS notification using the Plivo Messages API.
        Args:
            message_body (str, optional): The content of the SMS message to be sent. Defaults to "".
            to_phone_number (str, optional): The recipient's phone number. Defaults to "".
        """
        self.logger.debug("Notifying alert SMS via Plivo")

        if not to_phone_number:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert SMS via Plivo: to_phone_number is required"
            )
        client = plivo.RestClient(
            self.authentication_config.auth_id,
            self.authentication_config.auth_token,
        )
        try:
            self.logger.debug("Sending SMS via Plivo")
            client.messages.create(
                src=self.authentication_config.from_phone_number,
                dst=to_phone_number,
                text=message_body,
            )
            self.logger.debug("SMS sent via Plivo")
        except Exception as e:
            self.logger.warning(
                "Failed to send SMS via Plivo", extra={"reason": str(e)}
            )
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert SMS via Plivo: {e}"
            )


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

    plivo_auth_id = os.environ.get("PLIVO_AUTH_ID")
    plivo_auth_token = os.environ.get("PLIVO_AUTH_TOKEN")
    plivo_from_phone_number = os.environ.get("PLIVO_FROM_PHONE_NUMBER")
    plivo_to_phone_number = os.environ.get("PLIVO_TO_PHONE_NUMBER")
    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Plivo Input Provider",
        authentication={
            "auth_id": plivo_auth_id,
            "auth_token": plivo_auth_token,
            "from_phone_number": plivo_from_phone_number,
        },
    )
    provider = PlivoProvider(context_manager, provider_id="plivo", config=config)
    provider.validate_scopes()
    # Send SMS
    provider.notify(
        message_body="Keep Alert",
        to_phone_number=plivo_to_phone_number,
    )
