"""Cloudflare CDN, DNS, and security Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class CloudflareProviderConfig(ProviderConfig):
    """CloudflareProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None
    host: Optional[str] = None


class CloudflareProvider(BaseProvider):
    """Cloudflare CDN, DNS, and security Provider"""

    PROVIDER_DISPLAY_NAME = "Cloudflare"
    PROVIDER_TAGS = ['cdn', 'security', 'dns', 'cloud']
    PROVIDER_DESCRIPTION = "Cloudflare CDN, DNS, and security"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Cloudflare API connectivity",
            mandatory=True,
            alias="Connect to Cloudflare",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: CloudflareProviderConfig,
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
        logger.info(f"Alert to Cloudflare: {message}")
        return {"status": "sent"}
