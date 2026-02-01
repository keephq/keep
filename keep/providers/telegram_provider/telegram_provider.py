"""
TelegramProvider is a class that implements the BaseProvider interface for Telegram messages.
"""

import asyncio
import dataclasses
from typing import Literal, Optional

import pydantic
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

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

    PROVIDER_DISPLAY_NAME = "Telegram"
    PROVIDER_CATEGORY = ["Collaboration"]

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

    def _notify(
        self,
        chat_id: str = "",
        topic_id: Optional[int] = None,
        message: str = "",
        reply_markup: Optional[dict[str, dict[str, any]]] = None,
        reply_markup_layout: Literal["horizontal", "vertical"] = "horizontal",
        parse_mode: str = None,
        image_url: Optional[str] = None,
        caption_on_image: bool = False,
        **kwargs: dict,
    ):
        """
        Notify alert message to Telegram using the Telegram Bot API
        https://core.telegram.org/bots/api

        Args:
            chat_id (str): Unique identifier for the target chat or username of the target channel
            topic_id (int): Unique identifier for the target message thread (topic)
            message (str): Message to be sent
            reply_markup (dict): Inline keyboard markup to be attached to the message
            reply_markup_layout (str): Direction of the reply markup, could be "horizontal" or "vertical"
            parse_mode (str): Mode for parsing entities in the message text, could be "markdown" or "html"
            image_url (str, optional): URL of the image to be attached to the message
            caption_on_image (bool, optional): Whether to use the message as a caption for the image
        """
        self.logger.debug("Notifying alert message to Telegram")

        if not chat_id:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Telegram: chat_id is required"
            )

        parse_mode_mapping = {"markdown": ParseMode.MARKDOWN_V2, "html": ParseMode.HTML}
        parse_mode = parse_mode_mapping.get(parse_mode, None)

        loop = asyncio.new_event_loop()
        telegram_bot = telegram.Bot(token=self.authentication_config.bot_token)
        try:
            keyboard_markup = None
            if reply_markup is not None:
                buttons = []
                for text, params in reply_markup.items():
                    button = InlineKeyboardButton(text=text, **params)
                    buttons.append(button)

                if reply_markup_layout == "horizontal":
                    buttons = [buttons]
                elif reply_markup_layout == "vertical":
                    buttons = [[button] for button in buttons]
                else:
                    raise ProviderException(
                        f"{self.__class__.__name__} failed to notify alert message to Telegram: reply_markup_direction should be either horizontal or vertical"
                    )

                keyboard_markup = InlineKeyboardMarkup(
                    inline_keyboard=buttons,
                )

            if image_url:
                # If image URL is provided, send the image
                if caption_on_image:
                    # Send image with caption
                    task = loop.create_task(
                        telegram_bot.send_photo(
                            chat_id=chat_id,
                            photo=image_url,
                            caption=message,
                            reply_markup=keyboard_markup,
                            parse_mode=parse_mode,
                            message_thread_id=topic_id,
                        )
                    )
                else:
                    # Send message first, then image
                    if message:
                        msg_task = loop.create_task(
                            telegram_bot.send_message(
                                chat_id=chat_id,
                                text=message,
                                reply_markup=None,  # Attach markup to the image instead
                                parse_mode=parse_mode,
                                message_thread_id=topic_id,
                            )
                        )
                        loop.run_until_complete(msg_task)

                    # Send image without caption
                    task = loop.create_task(
                        telegram_bot.send_photo(
                            chat_id=chat_id,
                            photo=image_url,
                            reply_markup=keyboard_markup,
                            message_thread_id=topic_id,
                        )
                    )
            else:
                # Send regular text message if no image URL is provided
                task = loop.create_task(
                    telegram_bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        reply_markup=keyboard_markup,
                        parse_mode=parse_mode,
                        message_thread_id=topic_id,
                    )
                )

            loop.run_until_complete(task)
        except Exception as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Telegram: {e}"
            )

        self.logger.debug("Alert message notified to Telegram")


async def test_send_message():
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

    # Test with text only
    await provider.notify(
        message="Keep Alert",
        chat_id=telegram_chat_id,
    )

    # Test with image
    await provider.notify(
        message="Keep Alert with Graph",
        chat_id=telegram_chat_id,
        image_url="https://example.com/path/to/grafana/graph.png",
    )

    # Test with image and using message as caption
    await provider.notify(
        message="CPU Usage Alert",
        chat_id=telegram_chat_id,
        image_url="https://example.com/path/to/grafana/cpu_graph.png",
        caption_on_image=True,
    )


if __name__ == "__main__":
    import threading

    def run_in_thread():
        import asyncio

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        # Set it as the event loop for this thread
        asyncio.set_event_loop(loop)
        try:
            # Run your async function in this new loop
            loop.run_until_complete(test_send_message())
        finally:
            loop.close()

    # Create and start the thread
    thread = threading.Thread(target=run_in_thread)
    thread.start()
    # Wait for the thread to complete if needed
    thread.join()
