"""
OpenSearch Provider is a class that allows to ingest/digest data from OpenSearch.
"""

import dataclasses
import json
import logging

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

@pydantic.dataclasses.dataclass
class OpensearchProviderAuthConfig:
    """
    OpenSearch authentication configuration.
    """
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OpenSearch API Key",
            "hint": "Not strictly required for receiving webhook alerts depending on setup",
            "sensitive": True,
        },
        default="",
    )

class OpensearchProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "OpenSearch"

    PROVIDER_CATEGORY = ["Monitoring", "Logging", "Database"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for OpenSearch provider.
        """
        self.authentication_config = OpensearchProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" | None = None
    ) -> AlertDto | list[AlertDto]:
        logger.info("Formatting OpenSearch alert")

        # OpenSearch monitor alerts can be customized, but generally have identifying fields 
        # like `monitor_name`, `trigger_name`, `severity` etc.
        name = event.get("monitor_name", event.get("title", "OpenSearch Alert"))
        
        status_raw = str(event.get("state", event.get("status", "firing"))).lower()
        if status_raw in ["completed", "resolved", "ok", "green"]:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING
            
        severity_raw = str(event.get("severity", "info")).lower()
        if severity_raw in ["1", "critical", "high"]:
            severity = AlertSeverity.CRITICAL
        elif severity_raw in ["2", "3", "warning"]:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        # `trigger_name` is commonly used in OpenSearch alerting
        trigger_name = event.get("trigger_name", "")
        description = event.get("message", f"Alert triggered from OpenSearch: {trigger_name}")
        
        return AlertDto(
            id=event.get("monitor_id", name),
            name=name,
            status=status,
            severity=severity,
            source=["opensearch"],
            description=description,
            **event
        )

if __name__ == "__main__":
    pass
