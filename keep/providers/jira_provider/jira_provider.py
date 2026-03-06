"""Jira issue tracking provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class JiraProviderAuthConfig:
    api_token: str = dataclasses.field(metadata={"required": True, "description": "Jira API Token", "sensitive": True}, default="")
    domain: str = dataclasses.field(metadata={"required": True, "description": "Jira Domain"}, default="")

class JiraProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Jira"
    PROVIDER_CATEGORY = ["ITSM"]
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"https://{self.authentication_config.domain}.atlassian.net"

    def validate_config(self):
        self.authentication_config = JiraProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_key: str = "", summary: str = "", **kwargs: Dict[str, Any]):
        if not project_key or not summary:
            raise ProviderException("Project key and summary are required")
        payload = {"summary": summary, "project": {"key": project_key}}
        try:
            response = requests.post(f"{self.api_url}/rest/api/2/issue/", json=payload, headers={"Authorization": f"Bearer {self.authentication_config.api_token}"}, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Jira API error: {e}")
        self.logger.info(f"Jira issue created: {summary}")
        return {"status": "success", "summary": summary}
