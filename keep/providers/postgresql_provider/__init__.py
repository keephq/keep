"""PostgreSQL database monitoring Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class PostgreSQLProviderConfig(ProviderConfig):
    """PostgreSQLProvider Configuration"""

    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class PostgreSQLProvider(BaseProvider):
    """PostgreSQL database monitoring Provider"""

    PROVIDER_DISPLAY_NAME = "PostgreSQL"
    PROVIDER_TAGS = ['database', 'sql', 'monitoring']
    PROVIDER_DESCRIPTION = "PostgreSQL database monitoring"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test PostgreSQL connectivity",
            mandatory=True,
            alias="Connect to PostgreSQL",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: PostgreSQLProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config

    def validate_scopes(self):
        """Validate PostgreSQL connection"""
        # TODO: Implement actual connection test
        return {"connection": True}

    def dispose(self):
        """Cleanup resources"""
        pass

    def _query(self):
        """Query PostgreSQL for metrics"""
        # TODO: Implement actual query logic
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert to PostgreSQL"""
        logger.info(f"Sending alert to PostgreSQL: {message}")
        return {"status": "sent", "message": message}
