"""
SkyWalking Provider is a class that allows to ingest alarms from Apache SkyWalking.
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SkywalkingProviderAuthConfig:
    """
    SkyWalking authentication configuration.
    """

    host: Optional[pydantic.AnyHttpUrl] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SkyWalking UI/OAP host",
            "hint": "e.g. http://skywalking-oap:12800",
            "validation": "any_http_url",
        },
    )


class SkywalkingProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates the configuration.
        """
        self.authentication = SkywalkingProviderAuthConfig(**self.config.authentication)

    @staticmethod
    def _format_alert(
        event: dict, provider_id: str, tenant_id: str, **kwargs
    ) -> AlertDto:
        """
        Formats a SkyWalking alarm into a Keep alert.
        """
        # https://skywalking.apache.org/docs/main/next/en/setup/backend/backend-alarm/#webhook-callback
        # SkyWalking sends a list of alarms, but BaseProvider.format_alert handles list items individually
        
        tags = event.get("tags", [])
        labels = {tag.get("key"): tag.get("value") for tag in tags if "key" in tag}
        
        # Try to determine severity from tags
        severity_val = labels.get("level", "INFO").upper()
        if "CRITICAL" in severity_val:
            severity = AlertSeverity.CRITICAL
        elif "ERROR" in severity_val or "HIGH" in severity_val:
            severity = AlertSeverity.HIGH
        elif "WARNING" in severity_val:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        # Start time is in milliseconds
        start_time_ms = event.get("startTime")
        last_received = (
            datetime.datetime.fromtimestamp(start_time_ms / 1000.0).isoformat()
            if start_time_ms
            else datetime.datetime.now().isoformat()
        )

        return AlertDto(
            id=f"{event.get('scope')}-{event.get('name')}-{event.get('ruleName')}-{start_time_ms}",
            name=event.get("ruleName", "SkyWalking Alarm"),
            instance=event.get("name"),
            message=event.get("alarmMessage"),
            last_received=last_received,
            severity=severity,
            status=AlertStatus.FIRING,  # SkyWalking alarms are generally firing when sent via webhook
            source=["skywalking"],
            labels=labels,
            scope=event.get("scope"),
            provider_id=provider_id,
            **kwargs,
        )

    def format_alert(
        self, event: dict, provider_id: str, tenant_id: str, **kwargs
    ) -> AlertDto:
        return self._format_alert(event, provider_id, tenant_id, **kwargs)

    @property
    def webhook_markdown(self) -> str:
        return """To configure SkyWalking to send alarms to Keep:
1. In SkyWalking, configure the alarm webhook in `alarm-settings.yml`.
2. Add the Keep webhook URL to the `webhooks` section:
```yaml
webhooks:
  - url: {keep_webhook_api_url}
```
3. (Optional) If you use an API key, add it to the URL or as a header if SkyWalking supports it.
"""
