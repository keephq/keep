import dataclasses
from typing import Optional

import pydantic
from splunklib.client import connect

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SplunkProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Splunk API Key",
            "sensitive": True,
        }
    )

    host: str = dataclasses.field(
        metadata={
            "description": "Splunk Host (default is localhost)",
        },
        default="localhost",
    )
    port: int = dataclasses.field(
        metadata={
            "description": "Splunkd Port (default is 8089)",
        },
        default=8089,
    )


class SplunkProvider(BaseProvider):
    """Pull alerts and query incidents from Splunk."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="The user can connect to the client",
            mandatory=True,
            alias="Connect to the client",
        ),
        ProviderScope(
            name="list_all_objects",
            description="The user can get all the alerts",
            mandatory=True,
            alias="List all Alerts",
        ),
        ProviderScope(
            name="edit_own_objects",
            description="The user can edit and add webhook to saved_searches",
            mandatory=True,
            alias="Needed to connect to webhook",
        ),
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
        list_all_objects_scope = "NOT_FOUND"
        edit_own_object_scope = "NOT_FOUND"
        try:
            service = connect(
                token=self.authentication_config.api_key,
                host=self.authentication_config.host,
                port=self.authentication_config.port,
            )
            for user in service.users:
                user_roles = user.content["roles"]
                for role_name in user_roles:
                    perms = self.__get_role_capabilities(
                        role_name=role_name, service=service
                    )
                    if not list_all_objects_scope and "list_all_objects" in perms:
                        list_all_objects_scope = True
                    if not edit_own_object_scope and "edit_own_objects" in perms:
                        edit_own_object_scope = True
                    if list_all_objects_scope and edit_own_object_scope:
                        break

            scopes = {
                "authenticated": True,
                "list_all_objects": list_all_objects_scope,
                "edit_own_objects": edit_own_object_scope,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "connect_to_client": str(e),
                "list_all_objects": "UNAUTHENTICATED",
                "edit_own_objects": "UNAUTHENTICATED",
            }
        return scopes

    def validate_config(self):
        self.authentication_config = SplunkProviderAuthConfig(
            **self.config.authentication
        )

    def __get_role_capabilities(self, role_name, service):
        role = service.roles[role_name]
        return role.content["capabilities"] + role.content["imported_capabilities"]

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
        service = connect(
            token=self.authentication_config.api_key,
            host=self.authentication_config.host,
            port=self.authentication_config.port,
        )
        for saved_search in service.saved_searches:
            existing_webhook_url = saved_search["_state"]["content"].get(
                "action.webhook.param.url", None
            )
            if existing_webhook_url is None or existing_webhook_url != keep_api_url:
                saved_search.update(**creation_updation_kwargs).refresh()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["SplunkProvider"]
    ) -> AlertDto:
        if not provider_instance:
            raise Exception("Provider instance is required to format alert")

        search_id = event["sid"]
        service = connect(
            token=provider_instance.authentication_config.api_key,
            host=provider_instance.authentication_config.host,
            port=provider_instance.authentication_config.port,
        )
        saved_search = service.saved_searches[search_id]
        return AlertDto(
            id=event["sid"],
            name=event["search_name"],
            source=["splunk"],
            url=event["results_link"],
            severity=SplunkProvider.SEVERITIES_MAP.get(
                saved_search["_state"]["content"]["alert.severity"]
            ),
            description=saved_search["_state"]["content"]["description"],
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
