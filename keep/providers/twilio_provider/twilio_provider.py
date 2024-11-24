"""
TwilioProvider is a class that implements the BaseProvider interface for Twilio updates.
"""

import dataclasses

import pydantic
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class TwilioProviderAuthConfig:
    """Twilio authentication configuration."""

    account_sid: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Twilio Account SID",
            "sensitive": False,
            "documentation_url": "https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them",
        }
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Twilio API Token",
            "sensitive": True,
            "documentation_url": "https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them",
        }
    )

    from_phone_number: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Twilio Phone Number",
            "sensitive": False,
            "documentation_url": "https://www.twilio.com/en-us/guidelines/regulatory",
        }
    )


class TwilioProvider(BaseProvider):
    """Send SMS via Twilio."""

    PROVIDER_DISPLAY_NAME = "Twilio"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_sms",
            description="The API token has permission to send the SMS",
            mandatory=True,
            alias="Send SMS",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        twilio_client = Client(
            self.authentication_config.account_sid,
            self.authentication_config.api_token,
        )
        try:
            # from: 15005550006 is a magic number according to https://www.twilio.com/docs/messaging/tutorials/automate-testing
            twilio_client.messages.create(
                from_="+15005550006",
                to="+5571981265131",
                body="scope test",
            )
            validated_scopes["send_sms"] = True
        except TwilioRestException as e:
            # unfortunately, there is no API to get the enabled region, so we just try US and if it fails on "enabled for the region"
            # we assume the creds are valid but the region is not enabled (and that's ok)
            if "SMS has not been enabled for the region" in str(e):
                self.logger.debug(
                    "Twilio SMS is not enabled for the region, but that's ok"
                )
                validated_scopes["send_sms"] = True
            else:
                self.logger.warning(
                    "Failed to validate scope send_sms",
                    extra={"reason": str(e)},
                )
                validated_scopes["send_sms"] = str(e)
        # other unknown exception
        except Exception as e:
            self.logger.warning(
                "Failed to validate scope send_sms",
                extra={"reason": str(e)},
            )
            validated_scopes["send_sms"] = str(e)

        return validated_scopes

    def validate_config(self):
        self.authentication_config = TwilioProviderAuthConfig(
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
        Notify alert with twilio SMS
        """
        # extract the required params
        self.logger.debug("Notifying alert SMS via Twilio")

        if not to_phone_number:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert SMS via Twilio: to_phone_number is required"
            )
        twilio_client = Client(
            self.authentication_config.account_sid, self.authentication_config.api_token
        )
        try:
            self.logger.debug("Sending SMS via Twilio")
            twilio_client.messages.create(
                from_=self.authentication_config.from_phone_number,
                to=to_phone_number,
                body=message_body,
            )
            self.logger.debug("SMS sent via Twilio")
        except Exception as e:
            self.logger.warning(
                "Failed to send SMS via Twilio", extra={"reason": str(e)}
            )
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert SMS via Twilio: {e}"
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

    twilio_api_token = os.environ.get("TWILIO_API_TOKEN")
    twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_from_phone_number = os.environ.get("TWILIO_FROM_PHONE_NUMBER")
    twilio_to_phone_number = os.environ.get("TWILIO_TO_PHONE_NUMBER")
    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Twilio Input Provider",
        authentication={
            "api_token": twilio_api_token,
            "account_sid": twilio_account_sid,
            "from_phone_number": twilio_from_phone_number,
        },
    )
    provider = TwilioProvider(context_manager, provider_id="twilio", config=config)
    provider.validate_scopes()
    # Send SMS
    provider.notify(
        message_body="Keep Alert",
        to_phone_number=twilio_to_phone_number,
    )
