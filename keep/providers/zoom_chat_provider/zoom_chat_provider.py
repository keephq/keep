"""
ZoomChatProvider is a class that provides a way to send Zoom Chats programmatically using the Incoming Webhook Zoom application.
"""

import dataclasses
import http
import os
import time
from typing import Optional

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class ZoomChatProviderAuthConfig:
    """
    ZoomChatProviderAuthConfig holds the authentication information for the ZoomChatProvider.
    """
    
    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "name": "webhook_url",
            "description": "Zoom Incoming Webhook Url",
            "required": True,
            "sensitive": True,
            "validation": "https_url",
        },
    )
    authorization_token: str = dataclasses.field(
        metadata={
            "name": "authorization_token",
            "description": "Incoming Webhook Authorization Token",
            "required": True,
            "sensitive": True,
        },
    )
    account_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Zoom Account ID",
            "sensitive": True,
        }
    )
    client_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Zoom Client ID",
            "sensitive": True,
        }
    )
    client_secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Zoom Client Secret",
            "sensitive": True,
        }
    )


class ZoomChatProvider(BaseProvider):
    """Send alert message to Zoom Chat using the Incoming Webhook application."""

    PROVIDER_DISPLAY_NAME = "Zoom Chat"
    PROVIDER_TAGS = ["messaging"]
    PROVIDER_CATEGORY = ["Communication"]
    BASE_URL = "https://api.zoom.us/v2"
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="user:read:user:admin",
            description="View a Zoom user's details",
            mandatory=False,
            alias="View a Zoom user",
        ),
        ProviderScope(
            name="user:read:list_users:admin",
            description="List Zoom users",
            mandatory=False,
            alias="List Zoom users",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.access_token = None

    def validate_config(self):
        """Validates required configuration for Zoom Chat provider."""
        self.authentication_config = ZoomChatProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.webhook_url
            and not self.authentication_config.authorization_token
        ):
            raise Exception(
                "Zoom Incoming Webhook URL and authorization token are required."
            )

    def _get_access_token(self) -> str:
        """
        Get OAuth access token from Zoom.
        Returns:
            str: Access token
        """
        try:
            token_url = "https://zoom.us/oauth/token"
            auth = HTTPBasicAuth(
                self.authentication_config.client_id,
                self.authentication_config.client_secret,
            )
            data = {
                "grant_type": "account_credentials",
                "account_id": self.authentication_config.account_id,
            }
            response = requests.post(token_url, auth=auth, data=data)
            if response.status_code != 200:
                raise ProviderException(
                    f"Failed to get access token: {response.json()}"
                )
            return response.json()["access_token"]
        except Exception as e:
            raise ProviderException(f"Failed to get access token: {str(e)}")

    def _get_headers(self) -> dict:
        """
        Get headers for API requests.
        Returns:
            dict: Headers including authorization
        """
        if not self.access_token:
            self.access_token = self._get_access_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate scopes for the provider."""
        if not all(
            [
                self.authentication_config.account_id,
                self.authentication_config.client_id,
                self.authentication_config.client_secret,
            ]
        ):
            return {
                "user:read:user:admin": "OAuth credentials not configured",
                "user:read:list_users:admin": "OAuth credentials not configured",
            }
        try:
            # Test API access by listing users
            response = requests.get(
                f"{self.BASE_URL}/users", headers=self._get_headers()
            )
            if response.status_code != 200:
                raise Exception(f"Failed to validate scopes: {response.json()}")
            return {
                "user:read:user:admin": True,
                "user:read:list_users:admin": True,
            }
        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            return {
                "user:read:user:admin": str(e),
                "user:read:list_users:admin": str(e),
            }

    def dispose(self):
        """Clean up resources."""
        self.access_token = None
        pass

    def _get_zoom_userinfo(self, email: str) -> dict:
        """Get a user's information from Zoom API using email address."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/users/{email}",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                self.logger.info("User details retrieved successfully")
                return response.json()
            else:
                raise ProviderException(
                    f"Failed to retrieve user info for {email}: {response.status_code} - {response.text}"
                )
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Failed to retrieve user info: {str(e)}")

    def _notify(
        self,
        severity: str = "info",
        title: Optional[str] = "",
        message: str = "",
        tagged_users:  Optional[str] = "",
        details_url:  Optional[str] = "",
        **kwargs: dict,
    ) -> str:
        """
        Send a message to Zoom Chat using a Incoming Webhook URL.
        Args:
            title (str): The title to use for the message. (optional)
            message (str): The text message to send. Supports Markdown formatting.
            tagged_users (list): A list of Zoom user email addresses to tag. (optional)
            severity (str): The severity of the alert.
            details_url (str): A URL linking to more information. (optional)
        Raises:
            ProviderException: If the message could not be sent successfully.
        """
        self.logger.debug("Sending message to Zoom Chat Incoming Webhook")
        webhook_url = self.authentication_config.webhook_url
        authorization_token = self.authentication_config.authorization_token
        if not message:
            raise ProviderException("Message is required")

        def __send_message(url, body, headers, retries=3):
            for attempt in range(retries):
                try:
                    resp = requests.post(url, json=body, headers=headers)
                    if resp.status_code == http.HTTPStatus.OK:
                        return resp
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed with status code {resp.status_code}"
                    )
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(1)
            raise requests.exceptions.RequestException(
                f"Failed to notify message after {retries} attempts"
            )

        payload = {
            "content": {
                "settings": {
                    "default_sidebar_color": (
                        "#EF4444"
                        if severity == "critical"
                        else (
                            "#F97316"
                            if severity == "high"
                            else (
                                "#EAB308"
                                if severity == "warning"
                                else "#10B981" if severity == "low" else "#3B82F6"
                            )
                        )
                    )
                },
                "body": [
                    {
                        "type": "message",
                        "is_markdown_support": "true",
                        "text": message,
                    }
                ],
            }
        }

        # Conditionally add a title entry
        if title:
            payload["content"]["head"] = {
                "text": title,
                "style": {"bold": "true"},
            }

        # Conditionally add the "View More Details" entry
        if details_url:
            payload["content"]["body"].append(
                {"type": "message", "text": "View More Details", "link": details_url}
            )

        # Conditionally add tagged users
        if tagged_users:
            tagged_users_list = [user.strip() for user in tagged_users.split(",")]
            tagged_user_jid_list = []

            for user in tagged_users_list:
                try:
                    user_data = self._get_zoom_userinfo(user)
                    jid = user_data.get("jid")
                    display_name = user_data.get("display_name")
                    if jid and display_name:
                        tagged_user_jid_list.append(f"<!{jid}|{display_name}>")
                except ProviderException as e:
                    self.logger.warning(f"Failed to get info for user {user}: {e}")
                    continue

            if tagged_user_jid_list:
                tagged_user_string = " ".join(tagged_user_jid_list)
                payload["content"]["body"].insert(
                    0,
                    {
                        "type": "message",
                        "is_markdown_support": True,
                        "text": tagged_user_string,
                    },
                )

        request_headers = {
            "Authorization": authorization_token,
            "Content-Type": "application/json",
        }
        response = __send_message(webhook_url, body=payload, headers=request_headers)
        if response.status_code != http.HTTPStatus.OK:
            raise ProviderException(
                f"Failed to send message to Zoom Chat: {response.text}"
            )
        self.logger.debug("Alert message sent to Zoom Chat successfully")
        return "Alert message sent to Zoom Chat successfully"


if __name__ == "__main__":
    import logging

    # Set up logging
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

    # Get webhook details from environment
    webhook_url = os.environ.get("ZOOM_WEBHOOK_URL")
    webhook_auth_token = os.environ.get("ZOOM_WEBHOOK_AUTH_TOKEN")

    if not all([webhook_url, webhook_auth_token]):
        raise Exception(
            "ZOOM_WEBHOOK_URL and ZOOM_WEBHOOK_AUTH_TOKEN are required"
        )

    # Create context manager
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Initialize the provider and provider config
    config = ProviderConfig(
        name="Zoom Chat",
        description="Zoom Chat Output Provider",
        authentication={
            "webhook_url": webhook_url,
            "authorization_token": webhook_auth_token,
        },
    )

    # Initialize provider
    provider = ZoomChatProvider(
        context_manager=context_manager,
        provider_id="zoom_chat_provider",
        config=config,
    )

    provider.notify(message="Simple alert to Zoom chat.")
