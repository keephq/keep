"""Jira on-premise ticketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Jira2ProviderAuthConfig:
    server_url: str = dataclasses.field(
        metadata={"required": True, "description": "Jira Server URL"},
        default=""
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Username"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "API Token", "sensitive": True},
        default=""
    )

class Jira2Provider(BaseProvider):
    """Jira on-premise ticketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Jira Server"
    PROVIDER_CATEGORY = ["ITSM"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Jira2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_key: str = "", summary: str = "", description: str = "", issue_type: str = "Task", **kwargs: Dict[str, Any]):
        if not project_key or not summary:
            raise ProviderException("Project key and summary are required")

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description or summary,
                "issuetype": {"name": issue_type}
            }
        }

        try:
            response = requests.post(
                f"{self.authentication_config.server_url}/rest/api/2/issue",
                json=payload,
                auth=(self.authentication_config.username, self.authentication_config.api_token),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Jira API error: {e}")

        self.logger.info("Jira issue created")
        return {"status": "success", "key": response.json().get("key")}
