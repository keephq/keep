"""
Simple Console Output Provider
"""

import dataclasses
import datetime
import typing

import pydantic
from fastapi.datastructures import FormData

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class MailgunProviderAuthConfig:

    extraction: typing.Optional[dict[str, str]] = dataclasses.field(
        default=lambda: {},
        metadata={
            "description": "Extraction Rules",
            "type": "form",
        },
    )


class MailgunProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MailgunProviderAuthConfig(
            **self.config.authentication
        )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        return super().setup_webhook(tenant_id, keep_api_url, api_key, setup_alerts)

    @staticmethod
    def _format_alert(event: FormData) -> AlertDto:
        name = event["subject"]
        source = event["from"]
        message = event["stripped-text"]
        timestamp = datetime.datetime.fromtimestamp(
            float(event["timestamp"])
        ).isoformat()
        severity = "info"  # to extract
        status = "firing"  # to extract
        return AlertDto(
            name=name,
            source=[source],
            message=message,
            description=message,
            lastReceived=timestamp,
            severity=severity,
            status=status,
            raw_email={**event},
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = {
        "description": "Console Output Provider",
        "authentication": {},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="mock",
        provider_type="console",
        provider_config=config,
    )
    provider.notify(alert_message="Simple alert showing context with name: John Doe")
