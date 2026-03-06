"""GitLab Issues provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GitLabProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "GitLab Host URL"},
        default="https://gitlab.com"
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Access Token", "sensitive": True},
        default=""
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "Project ID"},
        default=""
    )

class GitLabProvider(BaseProvider):
    """GitLab Issues provider."""
    
    PROVIDER_DISPLAY_NAME = "GitLab"
    PROVIDER_CATEGORY = ["ITSM"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitLabProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", description: str = "", labels: str = "", **kwargs: Dict[str, Any]):
        if not title:
            raise ProviderException("Title is required")

        payload = {
            "title": title,
            "description": description or title
        }
        if labels:
            payload["labels"] = labels

        try:
            response = requests.post(
                f"{self.authentication_config.host}/api/v4/projects/{self.authentication_config.project_id}/issues",
                json=payload,
                headers={"PRIVATE-TOKEN": self.authentication_config.access_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GitLab API error: {e}")

        self.logger.info("GitLab issue created")
        return {"status": "success", "iid": response.json().get("iid")}
