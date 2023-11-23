"""
Keep Provider is a class that allows to ingest/digest data from Keep.
"""
import logging

from keep.api.core.db import get_alerts_with_filters
from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class KeepProvider(BaseProvider):
    """
    Automation on your alerts with Keep.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def _query(self, filters, **kwargs):
        """
        Query Keep for alerts.
        """
        alerts = get_alerts_with_filters(
            self.context_manager.tenant_id, filters=filters
        )
        return alerts

    def validate_config(self):
        """
        Validates required configuration for Keep provider.

        """
        pass

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        return AlertDto(
            **event,
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
