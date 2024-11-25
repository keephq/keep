import dataclasses
import enum

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


class S4Status(str, enum.Enum):
    """
    SIGNL4 alert status.
    """

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class S4AlertingScenario(str, enum.Enum):
    """
    SIGNL4 alerting scenario.
    """

    DEFAULT = ""
    SINGLE_ACK = "single_ack"
    MULTI_ACK = "multi_ack"
    EMERGENCY = "emergency"


@pydantic.dataclasses.dataclass
class Signl4ProviderAuthConfig:
    signl4_integration_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SIGNL4 integration or team secret",
            "sensitive": True,
        },
    )


class Signl4Provider(BaseProvider):
    """Trigger SIGNL4 alerts."""

    PROVIDER_DISPLAY_NAME = "SIGNL4"
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="signl4:create",
            description="Create SIGNL4 alerts",
            mandatory=True,
            alias="Create alerts",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Signl4ProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        try:
            self._notify(
                user="John Doe",
                title="Simple test alert from Keep",
                message="Simple alert showing context with name: John Doe. Please ignore.",
            )
            scopes["signl4:create"] = True
        except Exception as e:
            self.logger.exception("Failed to create SIGNL4 alert")
            scopes["signl4:create"] = str(e)
        return scopes

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        title: str | None = None,
        message: str | None = None,
        user: str | None = None,
        s4_external_id: str | None = None,
        s4_status: S4Status = S4Status.NEW,
        s4_service: str | None = None,
        s4_location: str | None = None,
        s4_alerting_scenario: S4AlertingScenario = S4AlertingScenario.DEFAULT,
        s4_filtering: bool = False,
        **kwargs: dict,
    ):
        """
        Create a SIGNL4 alert.
            Alert / Incident is created via the SIGNL4 Webhook API (https://connect.signl4.com/webhook/docs/index.html).

        Args:
            kwargs (dict): The providers with context
        """

        # Alert data
        alert_data = {
            "title": title,
            "message": message,
            "user": user,
            "X-S4-ExternalID": s4_external_id,
            "X-S4-Status": s4_status,
            "X-S4-Service": s4_service,
            "X-S4-Location": s4_location,
            "X-S4-AlertingScenario": s4_alerting_scenario,
            "X-S4-Filtering": s4_filtering,
            "X-S4-SourceSystem": "Keep",
            **kwargs,
        }

        # SIGNL4 webhook URL
        webhook_url = (
            "https://connect.signl4.com/webhook/"
            + self.authentication_config.signl4_integration_secret
        )

        try:
            result = requests.post(url=webhook_url, json=alert_data)

            if result.status_code == 201:
                # Success
                self.logger.info(result.text)
            else:
                # Error
                self.logger.exception("Error: " + str(result.status_code))
                raise Exception("Error: " + str(result.status_code))

        except:
            self.logger.exception("Failed to create SIGNL4 alert")
            raise


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    signl4_integration_secret = os.environ.get("SIGNL4_INTEGRATION_SECRET")
    assert signl4_integration_secret

    # Initalize the provider and provider config
    provider_config = ProviderConfig(
        description="SIGNL4 Provider",
        authentication={"signl4_integration_secret": signl4_integration_secret},
    )
    provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="keep-s4",
        provider_type="signl4",
        provider_config=provider_config,
    )
    # provider.notify(
    #     message="Simple alert showing context with name: John Doe",
    #     note="Simple alert",
    #     user="John Doe",
    # )
    provider.query(type="alerts", query="status: open")
