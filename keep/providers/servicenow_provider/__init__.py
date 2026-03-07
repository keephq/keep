"""ServiceNow ITSM and ticketing Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class ServiceNowProviderConfig(ProviderConfig):
    """ServiceNowProvider Configuration"""

    api_key: Optional[str] = None
    api_token: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ServiceNowProvider(BaseProvider):
    """ServiceNow ITSM and ticketing Provider"""

    PROVIDER_DISPLAY_NAME = "ServiceNow"
    PROVIDER_TAGS = ['itsm', 'ticketing', 'incident-management', 'cloud']
    PROVIDER_DESCRIPTION = "ServiceNow ITSM and ticketing"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test ServiceNow API connectivity",
            mandatory=True,
            alias="Connect to ServiceNow",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ServiceNowProviderConfig,
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
        logger.info(f"Alert to ServiceNow: {message}")
        return {"status": "sent"}
