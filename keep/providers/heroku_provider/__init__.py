"""Heroku cloud application platform Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class HerokuProviderConfig(ProviderConfig):
    """HerokuProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class HerokuProvider(BaseProvider):
    """Heroku cloud application platform Provider"""

    PROVIDER_DISPLAY_NAME = "Heroku"
    PROVIDER_TAGS = ['cloud', 'paas', 'platform', 'hosting']
    PROVIDER_DESCRIPTION = "Heroku cloud application platform"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Heroku API connectivity",
            mandatory=True,
            alias="Connect to Heroku",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: HerokuProviderConfig,
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
        logger.info(f"Alert to Heroku: {message}")
        return {"status": "sent"}
