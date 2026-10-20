import dataclasses
import hashlib
import http
import os
import time
from contextlib import ExitStack
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import pydantic
import redis
import requests
from redis.sentinel import Sentinel

from keep.api.core.config import config as keep_config
from keep.api.redis_settings import get_redis_settings
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


def _pacing_redis_client(stack):
    """Use Keep's existing Redis configuration; never a private delivery queue."""
    if not keep_config("REDIS", default=False, cast=bool):
        raise ProviderException("Google Chat rate limiting requires Keep Redis")
    settings = get_redis_settings()
    options = {
        "username": settings.username,
        "password": settings.password,
        "db": settings.database,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
        "ssl": settings.ssl,
    }
    if settings.ssl:
        options.update(
            ssl_cert_reqs=settings.ssl_cert_reqs,
            ssl_check_hostname=settings.ssl_check_hostname,
            ssl_ca_certs=settings.ssl_ca_certs,
        )
    if settings.sentinel:
        sentinel = Sentinel(
            settings.host,
            sentinel_kwargs={"socket_timeout": 2, "socket_connect_timeout": 2},
            **options,
        )
        for node in sentinel.sentinels:
            stack.callback(node.close)
        client = sentinel.master_for(settings.sentinel_master)
    else:
        client = redis.Redis(host=settings.host, port=settings.port, **options)
    stack.callback(client.close)
    return client


def _wait_for_space(client, webhook_url):
    """Coordinate all provider aliases for a Space without storing their secrets."""
    parsed = urlsplit(str(webhook_url))
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "chat.googleapis.com"
        or len(parts) != 4
        or parts[:2] != ["v1", "spaces"]
        or not parts[2]
        or parts[3] != "messages"
    ):
        raise ProviderException("Rate limiting requires a Google Chat webhook URL")
    space_hash = hashlib.sha256(parts[2].encode()).hexdigest()
    key = f"keep:google-chat:space:{space_hash}"
    deadline = time.monotonic() + 60
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderException("Google Chat space remained busy for 60 seconds")
        try:
            if client.set(key, "1", nx=True, px=1100):
                if time.monotonic() >= deadline:
                    raise ProviderException(
                        "Google Chat space remained busy for 60 seconds"
                    )
                return
            delay_ms = client.pttl(key)
        except redis.RedisError:
            raise ProviderException("Google Chat rate limiter unavailable") from None
        if delay_ms == -1:
            raise ProviderException("Google Chat rate limiter key has no expiry")
        remaining = max(0, deadline - time.monotonic())
        time.sleep(min(remaining, max(0.01, delay_ms / 1000)))


@pydantic.dataclasses.dataclass
class GoogleChatProviderAuthConfig:
    """Google Chat authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "name": "webhook_url",
            "description": "Google Chat Webhook Url",
            "required": True,
            "sensitive": True,
            "validation": "https_url",
        },
    )


class GoogleChatProvider(BaseProvider):
    """Send alert message to Google Chat."""

    PROVIDER_DISPLAY_NAME = "Google Chat"
    PROVIDER_TAGS = ["messaging"]
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GoogleChatProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, message="", **kwargs: dict):
        if not message:
            raise ProviderException("Message is required")
        with ExitStack() as stack:
            limiter = None
            if keep_config("GOOGLE_CHAT_RATE_LIMIT_ENABLED", default=False, cast=bool):
                limiter = _pacing_redis_client(stack)
            return self._send_message(message, limiter)

    def _send_message(self, message, limiter):
        """
        Notify a message to a Google Chat room using a webhook URL.

        Args:
            message (str): The text message to send.

        Raises:
            ProviderException: If the message could not be sent successfully.
        """
        self.logger.debug("Notifying message to Google Chat")
        webhook_url = self.authentication_config.webhook_url

        if not message:
            raise ProviderException("Message is required")

        payload = {"text": message}
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        retries = 3
        for attempt in range(retries):
            if limiter is not None:
                _wait_for_space(limiter, webhook_url)
            response = None
            try:
                response = requests.post(
                    webhook_url, json=payload, headers=headers, timeout=(5, 15)
                )
            except requests.exceptions.RequestException as error:
                # Request exception messages can contain the secret webhook URL.
                self.logger.warning(
                    "Google Chat attempt %s failed with %s",
                    attempt + 1,
                    type(error).__name__,
                )
            else:
                if response.status_code == http.HTTPStatus.OK:
                    self.logger.debug("Alert message sent to Google Chat successfully")
                    return "Alert message sent to Google Chat successfully"
                if response.status_code not in (408, 429) and not (
                    500 <= response.status_code < 600
                ):
                    raise ProviderException(
                        f"Google Chat rejected the message with status {response.status_code}"
                    )
                self.logger.warning(
                    "Google Chat attempt %s failed with status %s",
                    attempt + 1,
                    response.status_code,
                )
            if attempt < retries - 1:
                time.sleep(self._retry_delay(response, attempt))

        raise ProviderException(
            f"Failed to notify Google Chat after {retries} attempts"
        )

    @staticmethod
    def _retry_delay(response, attempt):
        """Respect Retry-After without blocking a worker for an unbounded period."""
        delay = 2**attempt
        retry_after = (
            response.headers.get("Retry-After") if response is not None else None
        )
        if retry_after:
            try:
                delay = max(delay, int(retry_after))
            except (TypeError, ValueError):
                try:
                    delay = max(
                        delay,
                        parsedate_to_datetime(retry_after).timestamp() - time.time(),
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
        if delay > 60:
            # Retrying sooner than the server requested would amplify rate limiting.
            raise ProviderException(
                "Google Chat Retry-After exceeds the 60 second limit"
            )
        return delay


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
