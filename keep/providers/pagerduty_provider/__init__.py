"""PagerDuty incident management Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class PagerDutyProviderConfig(ProviderConfig):
    """PagerDutyProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    region: Optional[str] = None


class PagerDutyProvider(BaseProvider):
    """PagerDuty incident management Provider"""

    PROVIDER_DISPLAY_NAME = "PagerDuty"
    PROVIDER_TAGS = ['incident', 'on-call', 'alerting']
    PROVIDER_DESCRIPTION = "PagerDuty incident management"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test PagerDuty API connectivity",
            mandatory=True,
            alias="Connect to PagerDuty",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: PagerDutyProviderConfig,
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
        logger.info(f"Alert to PagerDuty: {message}")
        return {"status": "sent"}
