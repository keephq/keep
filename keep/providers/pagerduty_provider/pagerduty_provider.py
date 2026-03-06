"""
PagerDuty provider for incident management.
"""

import dataclasses
from typing import Any, Dict

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PagerDutyProviderAuthConfig:
    routing_key: str = dataclasses.field(
        metadata={"required": True, "description": "PagerDuty Integration Key", "sensitive": True},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"description": "PagerDuty API Key for REST API", "sensitive": True},
        default=""
    )


class PagerDutyProvider(BaseProvider):
    """PagerDuty incident management provider."""

    PROVIDER_DISPLAY_NAME = "PagerDuty"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["alerting"]

    PAGERDUTY_API = "https://api.pagerduty.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PagerDutyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(
        self,
        summary: str = "",
        severity: str = "warning",
        source: str = "Keep",
        dedup_key: str = "",
        **kwargs: Dict[str, Any],
    ):
        """Send event to PagerDuty Events API v2."""
        if not self.authentication_config.routing_key:
            raise ProviderException("Routing key is required")

        if not summary:
            raise ProviderException("Summary is required")

        payload = {
            "routing_key": self.authentication_config.routing_key,
            "event_action": "trigger",
            "dedup_key": dedup_key or summary[:50],
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": source,
            }
        }

        try:
            response = requests.post(
                f"{self.PAGERDUTY_API}/events/v2/enqueue",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"PagerDuty API error: {e}")

        self.logger.info("PagerDuty event sent successfully")

        return {"status": "success", "dedup_key": payload["dedup_key"]}
