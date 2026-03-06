"""
Webhook provider is a generic provider for sending webhook notifications
to any HTTP endpoint with support for custom headers, authentication, and methods.
"""

import dataclasses
from typing import Any, Dict, Optional, Union

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WebhookProviderAuthConfig:
    """Webhook authentication configuration."""

    bearer_token: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Bearer token for authentication",
            "sensitive": True,
        },
        default="",
    )
    basic_auth_username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Username for Basic Authentication",
            "sensitive": False,
        },
        default="",
    )
    basic_auth_password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Password for Basic Authentication",
            "sensitive": True,
        },
        default="",
    )


class WebhookProvider(BaseProvider):
    """Send webhook notifications to custom HTTP endpoints."""

    PROVIDER_DISPLAY_NAME = "Webhook"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate provider configuration."""
        self.authentication_config = WebhookProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        url: str,
        method: str = "POST",
        headers: Union[Dict, str] = None,
        body: Union[Dict, str, None] = None,
        timeout: int = 30,
        **kwargs: Dict[str, Any],
    ):
        """
        Send a webhook notification to the specified URL.

        Args:
            url (str): The webhook URL to send the request to.
            method (str): HTTP method to use. Options: POST, PUT, PATCH. Default is POST.
            headers (Union[Dict, str]): Custom headers to include in the request. Can be a dict or JSON string.
            body (Union[Dict, str, None]): The request body/payload. Can be a dict or JSON string.
            timeout (int): Request timeout in seconds. Default is 30.

        Returns:
            dict: Response information including status code and response text.
        """
        self.logger.debug(
            "Sending webhook notification",
            extra={
                "url": url,
                "method": method,
                "provider_id": self.provider_id,
            },
        )

        # Validate URL
        if not url:
            raise ProviderException("URL is required for webhook notification")

        # Validate and normalize method
        method = method.upper()
        if method not in ["POST", "PUT", "PATCH"]:
            raise ProviderException(
                f"Invalid HTTP method: {method}. Must be one of: POST, PUT, PATCH"
            )

        # Parse headers if provided as string
        if headers and isinstance(headers, str):
            try:
                import json
                headers = json.loads(headers)
            except Exception as e:
                raise ProviderException(f"Failed to parse headers JSON: {e}")

        # Ensure headers is a dict
        if not headers:
            headers = {}

        # Set default Content-Type if not specified
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # Parse body if provided as string
        if body and isinstance(body, str):
            try:
                import json
                # Try to parse as JSON first
                parsed_body = json.loads(body)
                body = parsed_body
            except Exception:
                # If not valid JSON, use as-is (for text payloads)
                pass

        # Build request kwargs
        request_kwargs = {
            "url": url,
            "headers": headers,
            "timeout": timeout,
        }

        # Add authentication
        if self.authentication_config.bearer_token:
            request_kwargs["headers"]["Authorization"] = (
                f"Bearer {self.authentication_config.bearer_token}"
            )
        elif (
            self.authentication_config.basic_auth_username
            and self.authentication_config.basic_auth_password
        ):
            request_kwargs["auth"] = (
                self.authentication_config.basic_auth_username,
                self.authentication_config.basic_auth_password,
            )

        # Add body for methods that support it
        if body is not None and method in ["POST", "PUT", "PATCH"]:
            if isinstance(body, dict):
                request_kwargs["json"] = body
            else:
                request_kwargs["data"] = body

        # Send the request
        try:
            response = requests.request(method, **request_kwargs)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Webhook request failed: {e}")

        self.logger.debug(
            "Webhook notification sent successfully",
            extra={
                "status_code": response.status_code,
                "provider_id": self.provider_id,
            },
        )

        return {
            "status_code": response.status_code,
            "response_text": response.text,
            "success": True,
        }


if __name__ == "__main__":
    # Output debug messages
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Load environment variables for testing
    webhook_url = os.environ.get("WEBHOOK_URL", "https://httpbin.org/post")
    bearer_token = os.environ.get("WEBHOOK_BEARER_TOKEN", "")
    basic_user = os.environ.get("WEBHOOK_BASIC_USER", "")
    basic_pass = os.environ.get("WEBHOOK_BASIC_PASS", "")

    # Initialize the provider and provider config
    auth_config = {}
    if bearer_token:
        auth_config["bearer_token"] = bearer_token
    elif basic_user and basic_pass:
        auth_config["basic_auth_username"] = basic_user
        auth_config["basic_auth_password"] = basic_pass

    config = ProviderConfig(
        id="webhook-test",
        description="Webhook Output Provider",
        authentication=auth_config,
    )

    provider = WebhookProvider(context_manager, provider_id="webhook", config=config)

    # Test notification
    result = provider.notify(
        url=webhook_url,
        method="POST",
        headers={"X-Custom-Header": "test-value"},
        body={
            "message": "Test webhook notification from Keep",
            "alert": "Test Alert",
            "severity": "info",
        },
    )
    print(f"Result: {result}")
