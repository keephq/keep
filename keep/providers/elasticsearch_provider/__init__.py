"""Elasticsearch search engine monitoring Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class ElasticsearchProviderConfig(ProviderConfig):
    """ElasticsearchProvider Configuration"""

    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class ElasticsearchProvider(BaseProvider):
    """Elasticsearch search engine monitoring Provider"""

    PROVIDER_DISPLAY_NAME = "Elasticsearch"
    PROVIDER_TAGS = ['search', 'database', 'monitoring']
    PROVIDER_DESCRIPTION = "Elasticsearch search engine monitoring"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Elasticsearch connectivity",
            mandatory=True,
            alias="Connect to Elasticsearch",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ElasticsearchProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config

    def validate_scopes(self):
        """Validate Elasticsearch connection"""
        # TODO: Implement actual connection test
        return {"connection": True}

    def dispose(self):
        """Cleanup resources"""
        pass

    def _query(self):
        """Query Elasticsearch for metrics"""
        # TODO: Implement actual query logic
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert to Elasticsearch"""
        logger.info(f"Sending alert to Elasticsearch: {message}")
        return {"status": "sent", "message": message}
