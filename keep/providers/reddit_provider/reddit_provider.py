"""Reddit social media provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RedditProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Reddit Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Reddit Client Secret", "sensitive": True},
        default=""
    )
    refresh_token: str = dataclasses.field(
        metadata={"required": True, "description": "Reddit Refresh Token", "sensitive": True},
        default=""
    )

class RedditProvider(BaseProvider):
    """Reddit social media provider."""
    
    PROVIDER_DISPLAY_NAME = "Reddit"
    PROVIDER_CATEGORY = ["Social Media"]
    REDDIT_API = "https://oauth.reddit.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RedditProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, subreddit: str = "", title: str = "", text: str = "", **kwargs: Dict[str, Any]):
        if not subreddit or not title:
            raise ProviderException("Subreddit and title are required")

        payload = {
            "sr": subreddit,
            "title": title,
            "text": text or "",
            "kind": "self"
        }

        try:
            response = requests.post(
                f"{self.REDDIT_API}/api/submit",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.refresh_token}",
                    "User-Agent": "KeepProvider/1.0"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Reddit API error: {e}")

        self.logger.info(f"Reddit post created in r/{subreddit}")
        return {"status": "success", "subreddit": subreddit}
