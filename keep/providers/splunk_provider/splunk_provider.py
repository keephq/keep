import dataclasses

import pydantic
from splunklib.client import connect

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SplunkProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk Username",
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk Password",
            "sensitive": True,
        }
    )

    host: str = dataclasses.field(
        metadata={
            "description": "Splunk Host (default is localhost)",
        },
        default="localhost"
    )
    port: int = dataclasses.field(
        metadata={
            "description": "Splunkd Port (default is 8089)",
        },
        default=8089
    )


class SplunkProvider(BaseProvider):
    """Pull alerts and query incidents from Splunk."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_client",
            description="The user can connect to the client",
            mandatory=True,
            alias="Connect to the client",
        )
    ]

    SEVERITIES_MAP = {
        "1": AlertSeverity.LOW,
        "2": AlertSeverity.INFO,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.HIGH,
        "5": AlertSeverity.CRITICAL,
    }

    def __init__(
            self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            connect(username=self.authentication_config.username, password=self.authentication_config.password,
                    host=self.authentication_config.host, port=self.authentication_config.port)
            scopes = {
                "connect_to_client": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_client": str(e),
            }
        return scopes

    def validate_config(self):
        self.authentication_config = SplunkProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def setup_webhook(
            self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up Splunk webhook on all Alerts")
        creation_updation_kwargs = {
            "actions": "webhook",
            "action.webhook": "1",
            "action.webhook.param.url": keep_api_url,
        }
        service = connect(username=self.authentication_config.username, password=self.authentication_config.password,
                          host=self.authentication_config.host, port=self.authentication_config.port)
        for saved_search in service.saved_searches:
            existing_webhook_url = saved_search["_state"]["content"].get("action.webhook.param.url", None)
            if existing_webhook_url is None or existing_webhook_url != keep_api_url:
                print("REEE_LOGS_HERE: ", saved_search["path"], existing_webhook_url)
                saved_search.update(**creation_updation_kwargs).refresh()

    # @staticmethod
    def _format_alert(self, event: dict) -> AlertDto:
        search_id = event["sid"]
        service = connect(username=self.authentication_config.username, password=self.authentication_config.password,
                          host=self.authentication_config.host, port=self.authentication_config.port)
        saved_search = service.saved_searches[search_id]
        return AlertDto(
            id=event["sid"],
            name=event["search_name"],
            source=["splunk"],
            url=event["results_link"],
            severity=SplunkProvider.SEVERITIES_MAP.get(saved_search["_state"]["content"]["alert.severity"]),
            description=saved_search["_state"]["content"]["description"]
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
    import os

    api_key = os.environ.get("SPLUNK_API_KEY")

    provider_config = {
        "authentication": {"api_key": api_key},
    }
    provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="keep-pd",
        provider_type="splunk",
        provider_config=provider_config,
    )
    results = provider.setup_webhook(
        "keep",
        "https://eb8a-77-137-44-66.ngrok-free.app/alerts/event/splunk?provider_id=keep-pd",
        "just-a-test",
        True,
    )
