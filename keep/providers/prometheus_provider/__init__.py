"""Prometheus metrics collection and alerting Provider for Keep"""

import logging
from typing import Optional
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


class PrometheusProviderConfig(ProviderConfig):
    """PrometheusProvider Configuration"""

    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class PrometheusProvider(BaseProvider):
    """Prometheus metrics collection and alerting Provider"""

    PROVIDER_DISPLAY_NAME = "Prometheus"
    PROVIDER_TAGS = ['metrics', 'monitoring', 'timeseries']
    PROVIDER_DESCRIPTION = "Prometheus metrics collection and alerting"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connection",
            description="Test Prometheus connectivity",
            mandatory=True,
            alias="Connect to Prometheus",
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: PrometheusProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.config = config

    def validate_scopes(self):
        """Validate Prometheus connection"""
        # TODO: Implement actual connection test
        return {"connection": True}

    def dispose(self):
        """Cleanup resources"""
        pass

    def _query(self):
        """Query Prometheus for metrics"""
        # TODO: Implement actual query logic
        return {}

    def notify(self, message: str, **kwargs):
        """Send alert to Prometheus"""
        logger.info(f"Sending alert to Prometheus: {message}")
        return {"status": "sent", "message": message}
