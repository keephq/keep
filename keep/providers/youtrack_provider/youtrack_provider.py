"""
YoutrackProvider is a class that provides a way to create new issues in Youtrack.
"""
import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class YoutrackProviderAuthConfig:
    """
    YoutrackProviderAuthConfig is a class that holds the authentication information for the YoutrackProvider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "YouTrack Host URL",
            "hint": "e.g. https://example.youtrack.cloud",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "YouTrack Project ID",
            "hint": "e.g. 1-0",
            "sensitive": False,
        }
    )

    permanent_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "YouTrack Permanent Token",
            "sensitive": True,
        }
    )

class YoutrackProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "YouTrack"
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_CATEGORY = ["Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="create_issue",
            mandatory=True,
            alias="Create Issue",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass
    
    def validate_config(self):
        """
        Validates required configuration for Youtrack provider.
        """
        self.authentication_config = YoutrackProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate scopes for the provider
        """
        self.logger.info("Validating Youtrack provider scopes")
        try:
            url = self._get_url("issues")
            headers = self._get_auth_headers()
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Error getting issues from Youtrack: {e}")
            return {"create_issue": str(e)}
        return {"create_issue": True}
    
    def _create_issue(self, summary="", description=""):
        """
        Create an issue in Youtrack.
        """
        self.logger.info("Creating issue in Youtrack")
        try:
            url = self._get_url("issues")
            headers = self._get_auth_headers()
            data = {
                "summary": summary,
                "description": description,
                "project": {"id": self.authentication_config.project_id},
            }
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            self.logger.info("Successfully created issue in Youtrack", extra={"response": response.json()})
        except Exception as e:
            self.logger.error(f"Error creating issue in Youtrack: {e}")
            return str(e)
        return response.json()

    def _get_url(self, endpoint: str):
        return f"{self.authentication_config.host_url}/api/{endpoint}"
    
    def _get_auth_headers(self):
        """
        Get authentication headers for Youtrack.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.permanent_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _notify(self, summary="", description=""):
        self.logger.info("Creating issue in Youtrack")
        return self._create_issue(summary=summary, description=description)
    
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    youtrack_host_url = os.getenv("YOUTRACK_HOST_URL")
    youtrack_project_id = os.getenv("YOUTRACK_PROJECT_ID")
    youtrack_permanent_token = os.getenv("YOUTRACK_permanent_token")

    config = ProviderConfig(
        description="Youtrack Provider",
        authentication={
            "host_url": youtrack_host_url,
            "project_id": youtrack_project_id,
            "permanent_token": youtrack_permanent_token,
        },
    )

    provider = YoutrackProvider(context_manager, "youtrack", config)
    provider._notify(summary="Test Issue", description="This is a test issue")
