"""
TelegramProvider is a class that implements the BaseProvider interface for Telegram messages.
"""
import dataclasses

import pydantic
import telegram

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TelegramProviderAuthConfig:
    """Telegram authentication configuration."""

    bot_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Telegram Bot Token",
            "sensitive": True,
        }
    )


class TelegramProvider(BaseProvider):
    """Send alert message to Telegram."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TelegramProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    async def _notify(self, **kwargs: dict):
        """
        Notify alert message to Telegram using the Telegram Bot API
        https://core.telegram.org/bots/api

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Telegram")
        chat_id = kwargs.pop("chat_id", "")
        message = kwargs.pop("message", [])

        if not chat_id:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Telegram: chat_id is required"
            )
        telegram_bot = telegram.Bot(token=self.authentication_config.bot_token)
        try:
            await telegram_bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Telegram: {e}"
            )

        self.logger.debug("Alert message notified to Telegram")


async def send_message():
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Telegram Provider",
        authentication={"bot_token": telegram_bot_token},
    )
    provider = TelegramProvider(
        context_manager, provider_id="telegram-test", config=config
    )
    await provider.notify(
        message="Keep Alert",
        chat_id=telegram_chat_id,
    )


if __name__ == "__main__":
    # Send the message
    import asyncio

    asyncio.run(send_message())
