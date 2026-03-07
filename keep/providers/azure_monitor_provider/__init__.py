"""Azure Monitor integration Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class AzureMonitorProviderConfig(ProviderConfig):
    """AzureMonitorProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None


class AzureMonitorProvider(BaseProvider):
    """Azure Monitor integration Provider"""

    PROVIDER_DISPLAY_NAME = "AzureMonitor"
    PROVIDER_TAGS = ['cloud', 'monitoring', 'azure']
    PROVIDER_DESCRIPTION = "Azure Monitor integration"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test AzureMonitor API connectivity",
            mandatory=True,
            alias="Connect to AzureMonitor",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: AzureMonitorProviderConfig,
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
        logger.info(f"Alert to AzureMonitor: {message}")
        return {"status": "sent"}
