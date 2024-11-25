"""
SendGridProvider is a class that implements the SendGrid API and allows email sending through Keep.
"""

import dataclasses
import logging

import pydantic
from python_http_client.exceptions import ForbiddenError, UnauthorizedError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SendgridProviderAuthConfig:
    """
    SendGrid authentication configuration.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SendGrid API key",
            "hint": "https://sendgrid.com/docs/ui/account-and-settings/api-keys/",
            "sensitive": True,
        }
    )
    from_email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "From email address",
            "hint": "e.g. noreply@yourdomain.com",
        }
    )


class SendgridProvider(BaseProvider):
    """Send email using the SendGrid API."""

    PROVIDER_DISPLAY_NAME = "SendGrid"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="email.send",
            description="Send emails using SendGrid",
            mandatory=True,
            documentation_url="https://sendgrid.com/docs/API_Reference/api_v3.html",
            alias="Email Sender",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SendgridProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        try:
            sg = SendGridAPIClient(self.authentication_config.api_key)
            # Validate email.send scope by attempting to send a test email
            if any(scope.name == "email.send" for scope in self.PROVIDER_SCOPES):
                try:
                    test_email = Mail(
                        from_email=self.authentication_config.from_email,
                        to_emails=self.authentication_config.from_email,
                        subject="Test Email for Scope Validation",
                        html_content="<strong>This is a test email for validating SendGrid email.send scope</strong>",
                    )
                    response = sg.send(test_email)
                    if response.status_code >= 400:
                        raise Exception(
                            f"Failed to validate email.send scope: {response.body}"
                        )
                    scopes["email.send"] = True
                except UnauthorizedError:
                    self.logger.warning(
                        "Failed to validate email.send scope: Unauthorized"
                    )
                    scopes["email.send"] = (
                        "Unauthorized: Invalid API key or insufficient permissions."
                    )
                except ForbiddenError:
                    self.logger.warning(
                        "Failed to validate email.send scope: Forbidden"
                    )
                    scopes["email.send"] = (
                        "Forbidden: Insufficient permissions to send email."
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to validate email.send scope: {e}")
                    scopes["email.send"] = str(e)
        except Exception as e:
            self.logger.error(f"Failed to validate scopes: {e}")
            for scope in self.PROVIDER_SCOPES:
                scopes[scope.name] = str(e)
        self.logger.info("Scopes validated", extra=scopes)
        return scopes

    def _notify(self, to: str | list[str], subject: str, html: str, **kwargs) -> dict:
        """
        Send an email using the SendGrid API.

        Args:
            to (str | list[str]): To email address or list of email addresses
            subject (str): Email subject
            html (str): Email body
        """
        _from = self.authentication_config.from_email
        self.logger.info(
            "Sending email using SendGrid API",
            extra={
                "from": _from,
                "to": to,
                "subject": subject,
            },
        )

        if isinstance(to, str):
            to_emails = [to]
        else:
            to_emails = to

        message = Mail(
            from_email=_from,
            to_emails=to_emails,
            subject=subject,
            html_content=html,
            **kwargs,
        )

        try:
            sg = SendGridAPIClient(self.authentication_config.api_key)
            response = sg.send(message)

            if response.status_code >= 400:
                self.logger.error(
                    f"Failed to send email to {to} with subject {subject}: {response.body}"
                )
                raise Exception(f"Failed to send email: {response.body}")

            self.logger.info(f"Email sent to {to} with subject {subject}")
            return {
                "status_code": response.status_code,
                "body": (
                    response.body.decode("utf-8")
                    if isinstance(response.body, bytes)
                    else response.body
                ),
                "headers": {
                    k: v
                    for k, v in response.headers.items()
                    if isinstance(v, (str, int, float, bool, type(None)))
                },
            }
        except UnauthorizedError:
            self.logger.error(
                "Unauthorized: Invalid API key or insufficient permissions."
            )
            raise Exception(
                "Failed to send email: Unauthorized. Please check your API key and permissions."
            )
        except ForbiddenError:
            self.logger.error("Forbidden: Insufficient permissions to send email.")
            raise Exception(
                "Failed to send email: Forbidden. Your API key does not have the necessary permissions."
            )
        except Exception as e:
            self.logger.error(f"Exception occurred: {e}")
            raise Exception(f"Failed to send email: {str(e)}")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    import os

    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {"api_key": sendgrid_api_key, "from_email": from_email},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="sendgrid-test",
        provider_type="sendgrid",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    print(scopes)
    import yaml

    mail = yaml.safe_load(
        """to:
- "youremail@gmail.com"
- "youranotheremail@gmail.com"
subject: "Hello from Keep!"
html: "<strong>Test</strong> with HTML"
"""
    )
    response = provider._notify(**mail)
    print(response)
