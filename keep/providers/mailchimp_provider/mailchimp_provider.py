"""
MailchimpProvider is a class that implements the Mailchimp API and allows email sending through Keep.
"""

import dataclasses

import pydantic
from mailchimp_transactional import Client

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MailchimpProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mailchimp API key",
            "hint": "https://mandrillapp.com//settings",
            "sensitive": True,
        }
    )


class MailchimpProvider(BaseProvider):
    """Send email using the Mailchimp API."""

    PROVIDER_CATEGORY = ["Collaboration"]

    PROVIDER_DISPLAY_NAME = "Mailchimp"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_client",
            description="The user can connect to the client",
            mandatory=True,
            alias="Connect to the client",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            self.__generate_client()
            scopes = {
                "connect_to_client": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_client": str(e),
            }
        return scopes

    def __generate_client(self) -> Client:
        """
        Generates a Mailchimp client.
        """
        client = Client(api_key=self.authentication_config.api_key)
        return client

    def validate_config(self):
        self.authentication_config = MailchimpProviderAuthConfig(
            **self.config.authentication
        )

    def _notify(self, _from: str, to: str, subject: str, html: str, **kwargs) -> dict:
        """
        Send an email using the Mailchimp API.

        Args:
            _from (str): From email address
            to (str): To email address
            subject (str): Email subject
            html (str): Email body
        """
        self.logger.info(
            "Sending email using Mailchimp API",
            extra={
                "from": _from,
                "to": to,
                "subject": subject,
            },
        )

        client = self.__generate_client()
        res = client.messages.send(
            {
                "message": {
                    "from_email": _from,
                    "subject": subject,
                    "text": html,
                    "to": [{"email": to, "type": "to"}],
                }
            }
        )
        print(res)
        if res[0]["status"] != "sent":
            error = res[0]["reject_reason"]
            raise Exception("Failed to send email: " + error)
        return res[0]

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    import os

    mailchimp_api_key = os.environ.get("MAILCHIMP_API_KEY")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = ProviderConfig(
        authentication={"api_key": mailchimp_api_key},
    )
    provider = MailchimpProvider(
        context_manager, provider_id="mailchimp-test", config=config
    )
    response = provider.notify(
        "onboarding@mailchimp.dev",
        "youremail@gmail.com",
        "Hello World from Keep!",
        "<strong>Test</strong> with HTML",
    )
    print(response)
