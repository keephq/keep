"""GitLab repository provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class GitLabRepoProviderAuthConfig:
    access_token: str = dataclasses.field(metadata={"required": True, "description": "GitLab Access Token", "sensitive": True}, default="")
    gitlab_url: str = dataclasses.field(metadata={"required": True, "description": "GitLab URL"}, default="https://gitlab.com")

class GitLabRepoProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "GitLab Repo"
    PROVIDER_CATEGORY = ["Version Control"]
    
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitLabRepoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_id: str = "", **kwargs: Dict[str, Any]):
        if not project_id:
            raise ProviderException("Project ID is required")
        self.logger.info(f"GitLab repo accessed: {project_id}")
        return {"status": "success", "project_id": project_id}
