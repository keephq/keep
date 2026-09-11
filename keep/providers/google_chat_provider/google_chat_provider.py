import dataclasses
import http
import json
import os
import re
import time
import typing
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class GoogleChatProviderAuthConfig:
    """Google Chat authentication configuration."""

    webhook_url: typing.Optional[HttpsUrl] = dataclasses.field(
        default=None,
        metadata={
            "name": "webhook_url",
            "description": "Default Google Chat Webhook Url. Optional when every notification passes its own webhook_url",
            "required": False,
            "sensitive": True,
            "validation": "https_url",
        },
    )
    webhook_urls: typing.Union[str, dict] = dataclasses.field(
        default="",
        metadata={
            "name": "webhook_urls",
            "description": "JSON object mapping a space name to its webhook URL, so a notification can name a space instead of carrying its URL",
            "required": False,
            "sensitive": True,
            "type": "file",
            "file_type": "application/json",
        },
    )


class GoogleChatProvider(BaseProvider):
    """Send alert message to Google Chat."""

    PROVIDER_DISPLAY_NAME = "Google Chat"
    PROVIDER_TAGS = ["messaging"]
    PROVIDER_CATEGORY = ["Collaboration"]

    # Webhook URLs are credentials, they carry "key" and "token" in the query
    # string. Accepting one per notification means the host has to be checked,
    # otherwise the provider becomes an open relay.
    WEBHOOK_HOST = "chat.googleapis.com"
    SENSITIVE_QUERY_PARAMS = ("key", "token")

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GoogleChatProviderAuthConfig(
            **self.config.authentication
        )
        self.webhook_urls = self.__parse_webhook_urls(
            self.authentication_config.webhook_urls
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @classmethod
    def __redact(cls, text: str) -> str:
        """Redact webhook credentials from a text before it reaches the logs."""
        params = "|".join(cls.SENSITIVE_QUERY_PARAMS)
        return re.sub(rf"([?&](?:{params})=)[^&\s\"']+", r"\1<redacted>", text)

    @classmethod
    def __validate_webhook_url(cls, webhook_url: str) -> str:
        parsed = urlparse(webhook_url)
        if parsed.scheme != "https":
            raise ProviderException(
                f"Refusing to send a message over {parsed.scheme or 'an empty scheme'}, "
                "only https is allowed"
            )
        if parsed.netloc != cls.WEBHOOK_HOST:
            # userinfo is a credential of its own, keep it out of the message
            netloc = parsed.netloc
            if "@" in netloc:
                netloc = f"<redacted>@{netloc.rsplit('@', 1)[-1]}"
            raise ProviderException(
                f"Refusing to send a message to {netloc or 'an empty host'}, "
                f"only {cls.WEBHOOK_HOST} is allowed"
            )
        return webhook_url

    @classmethod
    def __parse_webhook_urls(cls, webhook_urls: typing.Union[str, dict]) -> dict:
        """Parse the space -> webhook URL map and validate every URL in it."""
        if not webhook_urls:
            return {}

        if isinstance(webhook_urls, str):
            try:
                webhook_urls = json.loads(webhook_urls)
            except json.JSONDecodeError as e:
                raise ProviderException(f"webhook_urls is not valid JSON: {e}")

        if not isinstance(webhook_urls, dict):
            raise ProviderException(
                "webhook_urls must be a JSON object mapping a space name to its webhook URL"
            )

        for space, webhook_url in webhook_urls.items():
            if not isinstance(webhook_url, str):
                raise ProviderException(
                    f"webhook_urls[{space}] must be a webhook URL string"
                )
            cls.__validate_webhook_url(webhook_url)

        return webhook_urls

    @staticmethod
    def __get_space_name(webhook_url: str) -> str:
        """Extract the space name from /v1/spaces/<space>/messages, for logging."""
        path = urlparse(webhook_url).path.strip("/").split("/")
        return path[2] if len(path) > 2 else "unknown"

    @staticmethod
    def __add_query_params(webhook_url: str, params: dict) -> str:
        """Merge query params into the webhook URL, keeping "key" and "token"."""
        parsed = urlparse(webhook_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(params)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def __resolve_webhook_url(self, space: str, webhook_url: str) -> str:
        """Resolve the space to post to, most explicit source first."""
        if webhook_url:
            return str(webhook_url)

        if space:
            if not self.webhook_urls:
                raise ProviderException(
                    f"Cannot resolve space {space}, no webhook_urls configured"
                )
            if space not in self.webhook_urls:
                raise ProviderException(f"Unknown space {space}")
            return self.webhook_urls[space]

        if self.authentication_config.webhook_url:
            return str(self.authentication_config.webhook_url)

        raise ProviderException(
            "No space to post to, pass space or webhook_url, or configure a default webhook_url"
        )

    def _notify(
        self,
        message: str = "",
        space: str = "",
        webhook_url: str = "",
        cards_v2: list = None,
        thread_key: str = "",
        **kwargs: dict,
    ):
        """
        Notify a message to a Google Chat space using a webhook URL.

        Args:
            message (str): The text message to send.
            space (str): Name of the space to post to, looked up in the webhook_urls of the provider configuration.
            webhook_url (str): Webhook URL of the space to post to, overrides both space and the provider configuration.
            cards_v2 (list): Google Chat cardsV2 payload, can be sent with or instead of the text message.
            thread_key (str): Arbitrary key that groups messages into a thread, a new thread is started if it is unknown.

        Raises:
            ProviderException: If the message could not be sent successfully.
        """
        webhook_url = self.__validate_webhook_url(
            self.__resolve_webhook_url(space, webhook_url)
        )

        if not message and not cards_v2:
            raise ProviderException("Either message or cards_v2 is required")

        self.logger.debug(
            "Notifying message to Google Chat",
            extra={"space": self.__get_space_name(webhook_url)},
        )

        def __send_message(url, body, headers, retries=3):
            last_error = ""
            for attempt in range(retries):
                try:
                    resp = requests.post(
                        url, json=body, headers=headers, allow_redirects=False
                    )
                    if resp.status_code == http.HTTPStatus.OK:
                        return resp

                    last_error = (
                        f"status code {resp.status_code}: {self.__redact(resp.text)}"
                    )
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed with {last_error}"
                    )

                except requests.exceptions.RequestException as e:
                    last_error = self.__redact(str(e))
                    self.logger.error(f"Attempt {attempt + 1} failed: {last_error}")

                if attempt < retries - 1:
                    time.sleep(1)

            raise requests.exceptions.RequestException(
                f"Failed to notify message after {retries} attempts, last error: {last_error}"
            )

        payload = {}
        if message:
            payload["text"] = message
        if cards_v2:
            payload["cardsV2"] = cards_v2
        if thread_key:
            payload["thread"] = {"threadKey": thread_key}
            webhook_url = self.__add_query_params(
                webhook_url,
                {"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"},
            )

        request_headers = {"Content-Type": "application/json; charset=UTF-8"}

        __send_message(webhook_url, body=payload, headers=request_headers)

        self.logger.debug("Alert message sent to Google Chat successfully")
        return "Alert message sent to Google Chat successfully"


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Load environment variables
    google_chat_webhook_url = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

    # Initialize the provider and provider config
    config = ProviderConfig(
        name="Google Chat",
        description="Google Chat Output Provider",
        authentication={"webhook_url": google_chat_webhook_url},
    )
    provider = GoogleChatProvider(
        context_manager, provider_id="google-chat", config=config
    )
    provider.notify(message="Simple alert showing context with name: John Doe")
