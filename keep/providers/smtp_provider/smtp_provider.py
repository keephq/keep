"""
SMTP Provider is a class that provides the functionality to send emails using SMTP protocol.
"""

import dataclasses
import typing
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTP_SSL

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import NoSchemeUrl, UrlPort


@pydantic.dataclasses.dataclass
class SmtpProviderAuthConfig:
    smtp_server: NoSchemeUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SMTP Server Address",
            "config_main_group": "authentication",
            "validation": "no_scheme_url",
        }
    )

    smtp_port: UrlPort = dataclasses.field(
        metadata={
            "required": True,
            "description": "SMTP port",
            "config_main_group": "authentication",
            "validation": "port",
        },
        default=587,
    )

    encryption: typing.Literal["SSL", "TLS", "None"] = dataclasses.field(
        default="TLS",
        metadata={
            "required": True,
            "description": "SMTP encryption",
            "type": "select",
            "options": ["SSL", "TLS", "None"],
            "config_main_group": "authentication",
        },
    )

    smtp_username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SMTP username",
            "config_main_group": "authentication",
        },
        default="",
    )

    smtp_password: str = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "SMTP password",
            "config_main_group": "authentication",
        },
        default="",
    )


class SmtpProvider(BaseProvider):
    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_email",
            mandatory=True,
            alias="Send Email",
        )
    ]
    PROVIDER_CATEGORY = ["Collaboration"]

    PROVIDER_TAGS = ["messaging"]
    PROVIDER_DISPLAY_NAME = "SMTP"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SmtpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate that the scopes provided are correct.
        """
        try:
            smtp = self.generate_smtp_client()
            smtp.quit()
            return {"send_email": True}
        except Exception as e:
            return {"send_email": str(e)}

    def generate_smtp_client(self):
        """
        Generate an SMTP client.
        """
        smtp_username = self.authentication_config.smtp_username
        smtp_password = self.authentication_config.smtp_password
        smtp_server = self.authentication_config.smtp_server
        smtp_port = self.authentication_config.smtp_port
        encryption = self.authentication_config.encryption

        if encryption == "SSL":
            smtp = SMTP_SSL(smtp_server, smtp_port)
        elif encryption == "TLS":
            smtp = SMTP(smtp_server, smtp_port)
            smtp.starttls()
        elif encryption == "None":
            smtp = SMTP(smtp_server, smtp_port)
        else:
            raise Exception(f"Invalid encryption: {encryption}")

        if smtp_username and smtp_password:
            smtp.login(smtp_username, smtp_password)

        return smtp

    def send_email(
        self, from_email: str, from_name: str, to_email: str, subject: str, body: str
    ):
        """
        Send an email using SMTP protocol.
        """
        msg = MIMEMultipart()
        if from_name == "":
            msg["From"] = from_email
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            smtp = self.generate_smtp_client()
            smtp.sendmail(from_email, to_email, msg.as_string())
            smtp.quit()

        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")

    def _notify(
        self, from_email: str, from_name: str, to_email: str, subject: str, body: str
    ):
        """
        Send an email using SMTP protocol.
        """
        self.send_email(from_email, from_name, to_email, subject, body)
        return {"from": from_email, "to": to_email, "subject": subject, "body": body}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    encryption = os.environ.get("ENCRYPTION")

    if smtp_username is None:
        raise Exception("SMTP_USERNAME is required")

    if smtp_password is None:
        raise Exception("SMTP_PASSWORD is required")

    if smtp_server is None:
        raise Exception("SMTP_SERVER is required")

    if smtp_port is None:
        raise Exception("SMTP_PORT is required")

    if encryption is None:
        raise Exception("ENCRYPTION is required")

    config = ProviderConfig(
        description="SMTP Provider",
        authentication={
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "encryption": encryption,
        },
    )

    smtp_provider = SmtpProvider(
        context_manager=context_manager,
        provider_id="smtp_provider",
        config=config,
    )

    smtp = smtp_provider.generate_smtp_client()
    smtp.quit()
