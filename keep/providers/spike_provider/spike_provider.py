"""
SpikeProvider is a class that implements the BaseProvider interface for Spike.sh incident alerts.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class SpikeProviderAuthConfig:
    """Spike.sh authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Spike.sh generic webhook URL (https://hooks.spike.sh/...)",
            "sensitive": True,
            "validation": "https_url",
            "documentation_url": "https://docs.spike.sh/integrations/generic-webhook",
        }
    )


class SpikeProvider(BaseProvider):
    """Send incident alerts to Spike.sh via webhook."""

    PROVIDER_DISPLAY_NAME = "Spike.sh"
    PROVIDER_CATEGORY = ["Incident Management"]

    VALID_STATUSES = {"critical", "warning", "info", "resolved"}

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SpikeProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(
        self,
        title: str = "",
        message: str = "",
        status: str = "critical",
        **kwargs: dict,
    ):
        """
        Fire an incident alert to Spike.sh.

        Args:
            title (str): Alert title shown in Spike.sh.
            message (str): Detailed description of the alert.
            status (str): Severity level — critical, warning, info, or resolved.
        """
        self.logger.debug("Sending incident alert to Spike.sh")

        if not title:
            raise ProviderException(
                f"{self.__class__.__name__}: title is required"
            )

        if status not in self.VALID_STATUSES:
            self.logger.warning(
                "Invalid Spike.sh status '%s', defaulting to 'critical'", status
            )
            status = "critical"

        payload = {
            "title": title,
            "description": message,
            "status": status,
        }

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send alert to Spike.sh: {e} — {e.response.text}"
            )
        except Exception as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send alert to Spike.sh: {e}"
            )

        self.logger.debug("Incident alert sent to Spike.sh")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Spike.sh Provider",
        authentication={
            "webhook_url": os.environ.get("SPIKE_WEBHOOK_URL"),
        },
    )
    provider = SpikeProvider(
        context_manager, provider_id="spike-test", config=config
    )
    provider.notify(
        title="Keep Alert",
        message="Test incident from Keep",
        status="critical",
    )
