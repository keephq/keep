"""
ZoomProvider is a class that provides a way to create Zoom meetings programmatically using Zoom's REST API.
"""

import dataclasses
import json
import os
from datetime import datetime
from typing import Optional

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ZoomProviderAuthConfig:
    """
    ZoomProviderAuthConfig holds the authentication information for the ZoomProvider.
    """

    account_id: str = dataclasses.field(
        metadata={"required": True, "description": "Zoom Account ID", "sensitive": True}
    )
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Zoom Client ID", "sensitive": True}
    )
    client_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zoom Client Secret",
            "sensitive": True,
        }
    )


class ZoomProvider(BaseProvider):
    """Create and manage Zoom meetings using REST API."""

    PROVIDER_DISPLAY_NAME = "Zoom"
    PROVIDER_CATEGORY = ["Communication", "Video Conferencing"]
    BASE_URL = "https://api.zoom.us/v2"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="create_meeting",
            description="Create a new Zoom meeting",
            mandatory=True,
            alias="Create Meeting",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.access_token = None

    def validate_config(self):
        """Validates required configuration for Zoom provider."""
        self.authentication_config = ZoomProviderAuthConfig(
            **self.config.authentication
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
        try:
            # Test API access by listing users
            response = requests.get(
                f"{self.BASE_URL}/users", headers=self._get_headers()
            )

            if response.status_code != 200:
                raise Exception(f"Failed to validate scopes: {response.json()}")

            return {"create_meeting": True}
        except Exception as e:
            self.logger.exception("Failed to validate scopes")
            return {"create_meeting": str(e)}

    def dispose(self):
        """Clean up resources."""
        self.access_token = None

    def _create_meeting(
        self,
        topic: str,
        start_time: datetime,
        duration: int = 60,
        timezone: str = "UTC",
        record_meeting: bool = False,
        host_email: Optional[str] = None,
    ) -> dict:
        """
        Create a new Zoom meeting.

        Args:
            topic: Meeting topic/name
            start_time: Meeting start time
            duration: Meeting duration in minutes
            timezone: Meeting timezone
            record_meeting: Whether to automatically record the meeting
            host_email: Email of the meeting host (optional)

        Returns:
            dict: Meeting details including join URL
        """
        try:
            # Format start time for Zoom API
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            meeting_settings = {
                "auto_recording": "cloud" if record_meeting else "none",
            }

            meeting_data = {
                "topic": topic,
                "type": 2,  # Scheduled meeting
                "start_time": start_time_str,
                "duration": duration,
                "timezone": timezone,
                "settings": meeting_settings,
            }

            # If host email provided, get their user ID first
            if host_email:
                users_response = requests.get(
                    f"{self.BASE_URL}/users/{host_email}",
                    headers=self._get_headers(),
                )

                if users_response.status_code != 200:
                    raise ProviderException(
                        f"Failed to find host: {users_response.json()}"
                    )

                user = users_response.json()
                user_id = user.get("id")
                if not user_id:
                    raise ProviderException(f"Host not found: {host_email}")
                create_url = f"{self.BASE_URL}/users/{user_id}/meetings"
            else:
                # Create meeting under authenticated user
                create_url = f"{self.BASE_URL}/users/me/meetings"

            response = requests.post(
                create_url, headers=self._get_headers(), data=json.dumps(meeting_data)
            )

            if response.status_code != 201:
                raise ProviderException(f"Failed to create meeting: {response.json()}")

            response = response.json()
            auto_recording = response.get("settings", {}).get("auto_recording")
            if record_meeting and not auto_recording == "cloud":
                # Zoom API failed to set auto recording
                self.logger.warning(
                    "Failed to set auto recording - do you have basic plan?",
                    extra={"auto_recording": auto_recording},
                )
            self.logger.info(
                "Meeting created successfully",
                extra={"meeting_id": response.get("id"), "recording": auto_recording},
            )
            return response

        except Exception as e:
            raise ProviderException(f"Failed to create meeting: {str(e)}")

    def _notify(
        self,
        topic: str,
        start_time: datetime = None,
        duration: int = 60,
        timezone: str = "UTC",
        record_meeting: bool = False,
        host_email: Optional[str] = None,
    ) -> dict:
        """
        Create a new Zoom meeting (notification endpoint).

        Returns:
            dict: Meeting details including join URL
        """
        try:
            self.logger.info(f"Creating new Zoom meeting: {topic}")
            if not start_time:
                start_time = datetime.now()
            meeting = self._create_meeting(
                topic=topic,
                start_time=start_time,
                duration=duration,
                timezone=timezone,
                record_meeting=record_meeting,
                host_email=host_email,
            )
            self.logger.info(
                "Meeting created successfully", extra={"meeting_id": meeting.get("id")}
            )
            return meeting
        except Exception as e:
            raise ProviderException(f"Failed to create meeting: {str(e)}")


if __name__ == "__main__":
    import logging
    from datetime import datetime, timedelta

    # Set up logging
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

    # Get authentication details from environment
    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")
    account_id = os.environ.get("ZOOM_ACCOUNT_ID")

    if not all([client_id, client_secret, account_id]):
        raise Exception(
            "ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, and ZOOM_ACCOUNT_ID are required"
        )

    # Create context manager
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Create provider config
    config = ProviderConfig(
        description="Zoom Provider",
        authentication={
            "client_id": client_id,
            "client_secret": client_secret,
            "account_id": account_id,
        },
    )

    # Initialize provider
    zoom_provider = ZoomProvider(
        context_manager=context_manager,
        provider_id="zoom_provider",
        config=config,
    )

    # Test meeting creation
    try:
        # Schedule meeting for tomorrow
        start_time = datetime.now() + timedelta(days=1)

        meeting = zoom_provider._notify(
            topic="Test Meeting",
            start_time=start_time,
            duration=30,
            timezone="UTC",
            record_meeting=True,
            host_email="shahar@keephq.dev",  # Replace with actual host email
        )

        print("Meeting created successfully!")
        print(f"Join URL: {meeting.get('join_url')}")
        print(f"Meeting ID: {meeting.get('id')}")
        print(f"Meeting Password: {meeting.get('password')}")

    except Exception as e:
        print(f"Failed to create meeting: {str(e)}")
