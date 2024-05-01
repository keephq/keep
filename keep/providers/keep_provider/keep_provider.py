"""
Keep Provider is a class that allows to ingest/digest data from Keep.
"""

import logging
from typing import Optional

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

    def _query(self, filters, distinct=True, time_delta=1, **kwargs):
        """
        Query Keep for alerts.
        """
        self.logger.info(
            "Querying Keep for alerts",
            extra={
                "filters": filters,
                "is_distinct": distinct,
                "time_delta": time_delta,
            },
        )
        db_alerts = get_alerts_with_filters(
            self.context_manager.tenant_id, filters=filters, time_delta=time_delta
        )
        self.logger.info(
            "Got alerts from Keep", extra={"num_of_alerts": len(db_alerts)}
        )

        fingerprints = {}
        alerts = []
        if db_alerts:
            for alert in db_alerts:
                if fingerprints.get(alert.fingerprint) and distinct is True:
                    continue
                alert_event = alert.event
                if alert.alert_enrichment:
                    alert_event["enrichments"] = alert.alert_enrichment.enrichments
                alerts.append(alert_event)
                fingerprints[alert.fingerprint] = True
        self.logger.info(
            "Returning alerts",
            extra={
                "num_of_alerts": len(alerts),
                "fingerprints": list(fingerprints.keys()),
            },
        )
        return alerts

    def validate_config(self):
        """
        Validates required configuration for Keep provider.

        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["KeepProvider"] = None
    ) -> AlertDto:
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
