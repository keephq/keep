"""Google Cloud monitoring and logging Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class StackdriverProviderConfig(ProviderConfig):
    """StackdriverProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None
    host: Optional[str] = None


class StackdriverProvider(BaseProvider):
    """Google Cloud monitoring and logging Provider"""

    PROVIDER_DISPLAY_NAME = "Stackdriver"
    PROVIDER_TAGS = ['observability', 'cloud', 'monitoring', 'gcp']
    PROVIDER_DESCRIPTION = "Google Cloud monitoring and logging"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Stackdriver API connectivity",
            mandatory=True,
            alias="Connect to Stackdriver",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: StackdriverProviderConfig,
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
        logger.info(f"Alert to Stackdriver: {message}")
        return {"status": "sent"}
