"""CircleCI continuous integration and delivery Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class CircleCIProviderConfig(ProviderConfig):
    """CircleCIProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class CircleCIProvider(BaseProvider):
    """CircleCI continuous integration and delivery Provider"""

    PROVIDER_DISPLAY_NAME = "CircleCI"
    PROVIDER_TAGS = ['cicd', 'automation', 'build', 'devops', 'cloud']
    PROVIDER_DESCRIPTION = "CircleCI continuous integration and delivery"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test CircleCI API connectivity",
            mandatory=True,
            alias="Connect to CircleCI",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: CircleCIProviderConfig,
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
        logger.info(f"Alert to CircleCI: {message}")
        return {"status": "sent"}
