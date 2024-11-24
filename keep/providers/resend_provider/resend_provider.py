"""
ResendProvider is a class that implements the Resend API and allows email sending through Keep.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ResendProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Resend API key",
            "hint": "https://resend.com/api-keys",
            "sensitive": True,
        }
    )


class ResendProvider(BaseProvider):
    """Send email using the Resend API."""

    PROVIDER_DISPLAY_NAME = "Resend"
    PROVIDER_CATEGORY = ["Collaboration"]

    RESEND_API_URL = "https://api.resend.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ResendProviderAuthConfig(
            **self.config.authentication
        )

    def _notify(self, _from: str, to: str, subject: str, html: str, **kwargs) -> dict:
        """
        Send an email using the Resend API.

        Args:
            _from (str): From email address
            to (str): To email address
            subject (str): Email subject
            html (str): Email body
        """
        self.logger.info(
            "Sending email using Resend API",
            extra={
                "from": _from,
                "to": to,
                "subject": subject,
            },
        )
        # until https://github.com/resendlabs/resend-python/pull/37/files is merged
        response = requests.post(
            f"{self.RESEND_API_URL}/emails",
            json={
                "from": _from,
                "to": to,
                "subject": subject,
                "html": html,
                **kwargs,
            },
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.authentication_config.api_key}",
            },
        )
        if response.status_code != 200:
            error = response.json()
            raise Exception("Failed to send email: " + error["message"])
        return response.json()

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    import os

    resend_api_key = os.environ.get("RESEND_API_KEY")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = ProviderConfig(
        id="resend-test",
        authentication={"api_key": resend_api_key},
    )
    provider = ResendProvider(context_manager, provider_id="resend-test", config=config)
    response = provider.notify(
        "onboarding@resend.dev",
        "youremail@gmail.com",
        "Hello World from Keep!",
        "<strong>Test</strong> with HTML",
    )
    print(response)
