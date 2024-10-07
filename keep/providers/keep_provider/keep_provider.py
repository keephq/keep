"""
Keep Provider is a class that allows to ingest/digest data from Keep.
"""

import logging

from keep.api.core.db import get_alerts_with_filters
from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.searchengine.searchengine import SearchEngine


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

    def _query(self, filters=None, version=1, distinct=True, time_delta=1, **kwargs):
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
        if version == 1:
            # filters are mandatory for version 1
            if not filters:
                raise ValueError("Filters are required for version")
            db_alerts = get_alerts_with_filters(
                self.context_manager.tenant_id, filters=filters, time_delta=time_delta
            )
            fingerprints = {}
            # distinct if needed
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
        else:
            search_engine = SearchEngine(tenant_id=self.context_manager.tenant_id)
            _filter = kwargs.get("filter")
            if not _filter:
                raise ValueError("Filter is required for version 2")
            try:
                alerts = search_engine.search_alerts_by_cel(
                    cel_query=_filter, limit=kwargs.get("limit"), timeframe=time_delta
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to search alerts by CEL: %s",
                    str(e),
                )
                raise
        self.logger.info("Got alerts from Keep", extra={"num_of_alerts": len(alerts)})
        return alerts

    def validate_config(self):
        """
        Validates required configuration for Keep provider.

        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" | None = None
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
