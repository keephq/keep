"""Telegram Bot provider for notifications."""

import dataclasses
from typing import Any, Dict

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TelegramProviderAuthConfig:
    bot_token: str = dataclasses.field(
        metadata={"required": True, "description": "Telegram Bot Token", "sensitive": True},
        default=""
    )
    chat_id: str = dataclasses.field(
        metadata={"required": True, "description": "Chat ID to send messages to"},
        default=""
    )


class TelegramProvider(BaseProvider):
    """Telegram Bot provider."""

    PROVIDER_DISPLAY_NAME = "Telegram"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    TELEGRAM_API = "https://api.telegram.org"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TelegramProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", parse_mode: str = "Markdown", **kwargs: Dict[str, Any]):
        """Send message via Telegram Bot API."""
        if not message:
            raise ProviderException("Message is required")

        url = f"{self.TELEGRAM_API}/bot{self.authentication_config.bot_token}/sendMessage"

        payload = {
            "chat_id": self.authentication_config.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Telegram API error: {e}")

        self.logger.info("Telegram message sent successfully")
        return {"status": "success"}
