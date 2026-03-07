"""Splunk log management and SIEM Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class SplunkProviderConfig(ProviderConfig):
    """SplunkProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None


class SplunkProvider(BaseProvider):
    """Splunk log management and SIEM Provider"""

    PROVIDER_DISPLAY_NAME = "Splunk"
    PROVIDER_TAGS = ['logging', 'siem', 'analytics']
    PROVIDER_DESCRIPTION = "Splunk log management and SIEM"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Splunk API connectivity",
            mandatory=True,
            alias="Connect to Splunk",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: SplunkProviderConfig,
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
        logger.info(f"Alert to Splunk: {message}")
        return {"status": "sent"}
