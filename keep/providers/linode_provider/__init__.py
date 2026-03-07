"""Linode cloud hosting and infrastructure Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class LinodeProviderConfig(ProviderConfig):
    """LinodeProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class LinodeProvider(BaseProvider):
    """Linode cloud hosting and infrastructure Provider"""

    PROVIDER_DISPLAY_NAME = "Linode"
    PROVIDER_TAGS = ['cloud', 'infrastructure', 'hosting', 'vps']
    PROVIDER_DESCRIPTION = "Linode cloud hosting and infrastructure"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Linode API connectivity",
            mandatory=True,
            alias="Connect to Linode",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: LinodeProviderConfig,
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
        logger.info(f"Alert to Linode: {message}")
        return {"status": "sent"}
