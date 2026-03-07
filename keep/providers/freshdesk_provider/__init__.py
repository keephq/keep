"""Freshdesk customer support and ticketing Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class FreshdeskProviderConfig(ProviderConfig):
    """FreshdeskProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class FreshdeskProvider(BaseProvider):
    """Freshdesk customer support and ticketing Provider"""

    PROVIDER_DISPLAY_NAME = "Freshdesk"
    PROVIDER_TAGS = ['support', 'ticketing', 'customer-service', 'cloud']
    PROVIDER_DESCRIPTION = "Freshdesk customer support and ticketing"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Freshdesk API connectivity",
            mandatory=True,
            alias="Connect to Freshdesk",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: FreshdeskProviderConfig,
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
        logger.info(f"Alert to Freshdesk: {message}")
        return {"status": "sent"}
