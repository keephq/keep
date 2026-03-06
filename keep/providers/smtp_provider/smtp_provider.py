"""SMTP Email provider using direct SMTP."""

import dataclasses
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SMTPProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "SMTP Server Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"required": True, "description": "SMTP Server Port"},
        default=587
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "SMTP Username"},
        default=""
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "SMTP Password", "sensitive": True},
        default=""
    )
    from_email: str = dataclasses.field(
        metadata={"required": True, "description": "From Email Address"},
        default=""
    )
    use_tls: bool = dataclasses.field(
        metadata={"description": "Use TLS"},
        default=True
    )

class SMTPProvider(BaseProvider):
    """SMTP Email provider."""
    
    PROVIDER_DISPLAY_NAME = "SMTP"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["email"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SMTPProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", body: str = "", html: bool = False, **kwargs: Dict[str, Any]):
        if not to or not subject or not body:
            raise ProviderException("To, subject, and body are required")

        msg = MIMEMultipart() if html else MIMEText(body)
        msg['From'] = self.authentication_config.from_email
        msg['To'] = to
        msg['Subject'] = subject

        if html:
            msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(self.authentication_config.host, self.authentication_config.port) as server:
                if self.authentication_config.use_tls:
                    server.starttls()
                server.login(self.authentication_config.username, self.authentication_config.password)
                server.send_message(msg)
        except Exception as e:
            raise ProviderException(f"SMTP error: {e}")

        self.logger.info("Email sent via SMTP")
        return {"status": "success"}
