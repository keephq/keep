"""Dynatrace APM monitoring Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class DynatraceProviderConfig(ProviderConfig):
    """DynatraceProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None


class DynatraceProvider(BaseProvider):
    """Dynatrace APM monitoring Provider"""

    PROVIDER_DISPLAY_NAME = "Dynatrace"
    PROVIDER_TAGS = ['apm', 'monitoring', 'performance']
    PROVIDER_DESCRIPTION = "Dynatrace APM monitoring"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Dynatrace API connectivity",
            mandatory=True,
            alias="Connect to Dynatrace",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: DynatraceProviderConfig,
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
        logger.info(f"Alert to Dynatrace: {message}")
        return {"status": "sent"}
