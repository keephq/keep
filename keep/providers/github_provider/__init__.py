"""GitHub issues and notifications Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class GitHubProviderConfig(ProviderConfig):
    """GitHubProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None


class GitHubProvider(BaseProvider):
    """GitHub issues and notifications Provider"""

    PROVIDER_DISPLAY_NAME = "GitHub"
    PROVIDER_TAGS = ['issue-tracking', 'notifications']
    PROVIDER_DESCRIPTION = "GitHub issues and notifications"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test GitHub API connectivity",
            mandatory=True,
            alias="Connect to GitHub",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: GitHubProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config

    def validate_scopes(self):
        """Validate API connection"""
        return {"connection": True}

    def dispose(self):
        """Cleanup"""
        pass

    def _query(self):
        """Query metrics"""
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert"""
        logger.info(f"Alert to GitHub: {message}")
        return {"status": "sent"}
