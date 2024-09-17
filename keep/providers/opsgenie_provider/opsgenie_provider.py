import dataclasses
import typing

import opsgenie_sdk
import pydantic
from opsgenie_sdk.rest import ApiException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class OpsgenieProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Ops genie api key (https://support.atlassian.com/opsgenie/docs/api-key-management/)",
            "sensitive": True,
        },
    )


class OpsGenieRecipient(pydantic.BaseModel):
    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/Recipient.md
    type: str
    id: typing.Optional[str] = None


class OpsgenieProvider(BaseProvider):
    """Create incidents in OpsGenie."""

    PROVIDER_DISPLAY_NAME = "OpsGenie"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="opsgenie:create",
            description="Create OpsGenie alerts",
            mandatory=True,
            alias="Create alerts",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Close an alert",
            func_name="close_alert",
            scopes=["opsgenie:create"],
            description="Close an alert",
            type="action",
        ),
        ProviderMethod(
            name="Comment an alert",
            func_name="comment_alert",
            scopes=["opsgenie:create"],
            description="Comment an alert",
            type="action",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.configuration = opsgenie_sdk.Configuration()
        self.configuration.api_key["Authorization"] = self.authentication_config.api_key

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        try:
            self._create_alert(
                user="John Doe",
                note="Simple alert",
                message="Simple alert showing context with name: John Doe",
            )
            scopes["opsgenie:create"] = True
        except ApiException as e:
            self.logger.exception("Failed to create OpsGenie alert")
            scopes["opsgenie:create"] = str(e)
        except Exception as e:
            self.logger.exception("Failed to create OpsGenie alert")
            scopes["opsgenie:create"] = str(e)
        return scopes

    def validate_config(self):
        self.authentication_config = OpsgenieProviderAuthConfig(
            **self.config.authentication
        )

    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/CreateAlertPayload.md
    def _create_alert(
        self,
        user: str | None = None,
        note: str | None = None,
        source: str | None = None,
        message: str | None = None,
        alias: str | None = None,
        description: str | None = None,
        responders: typing.List[OpsGenieRecipient] | None = None,
        visible_to: typing.List[OpsGenieRecipient] | None = None,
        actions: typing.List[str] | None = None,
        tags: typing.List[str] | None = None,
        details: typing.Dict[str, str] | None = None,
        entity: str | None = None,
        priority: str | None = None,
    ):
        """
        Creates OpsGenie Alert.

        """
        api_instance = opsgenie_sdk.AlertApi(opsgenie_sdk.ApiClient(self.configuration))
        create_alert_payload = opsgenie_sdk.CreateAlertPayload(
            user=user,
            note=note,
            source=source,
            message=message,
            alias=alias,
            description=description,
            responders=responders,
            visible_to=visible_to,
            actions=actions,
            tags=tags,
            details=details,
            entity=entity,
            priority=priority,
        )
        try:
            api_instance.create_alert(create_alert_payload)
        except ApiException:
            self.logger.exception("Failed to create OpsGenie alert")
            raise

    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/CloseAlertPayload.md
    def close_alert(
        self,
        alert_id: str,
    ):
        """
        Close OpsGenie Alert.

        """
        self.logger.info("Closing Opsgenie alert", extra={"alert_id": alert_id})
        api_instance = opsgenie_sdk.AlertApi(opsgenie_sdk.ApiClient(self.configuration))
        close_alert_payload = opsgenie_sdk.CloseAlertPayload()
        try:
            api_instance.close_alert(alert_id, close_alert_payload=close_alert_payload)
            self.logger.info("Opsgenie Alert Closed", extra={"alert_id": alert_id})
        except ApiException:
            self.logger.exception("Failed to close OpsGenie alert")
            raise

    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/AddNoteToAlertPayload.md
    def comment_alert(
        self,
        alert_id: str,
        note: str,
    ):
        """
        Add comment or note to an OpsGenie Alert.

        """
        self.logger.info("Commenting Opsgenie alert", extra={"alert_id": alert_id})
        api_instance = opsgenie_sdk.AlertApi(opsgenie_sdk.ApiClient(self.configuration))
        add_note_to_alert_payload = opsgenie_sdk.AddNoteToAlertPayload(
            note=note,
        )
        try:
            api_instance.add_note(alert_id, add_note_to_alert_payload)
            self.logger.info("Opsgenie Alert Commented", extra={"alert_id": alert_id})
        except ApiException:
            self.logger.exception("Failed to comment OpsGenie alert")
            raise

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        user: str | None = None,
        note: str | None = None,
        source: str | None = None,
        message: str | None = None,
        alias: str | None = None,
        description: str | None = None,
        responders: typing.List[OpsGenieRecipient] | None = None,
        visible_to: typing.List[OpsGenieRecipient] | None = None,
        actions: typing.List[str] | None = None,
        tags: typing.List[str] | None = None,
        details: typing.Dict[str, str] | None = None,
        entity: str | None = None,
        priority: str | None = None,
        **kwargs: dict,
    ):
        """
        Create a OpsGenie alert.
            Alert/Incident is created either via the Events API or the Incidents API.
            See https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3 for more information

        Args:
            kwargs (dict): The providers with context
        """
        self._create_alert(
            user,
            note,
            source,
            message,
            alias,
            description,
            responders,
            visible_to,
            actions,
            tags,
            details,
            entity,
            priority,
            **kwargs,
        )

    def _query(self, query_type="", query="", **kwargs: dict):
        api_instance = opsgenie_sdk.AlertApi(opsgenie_sdk.ApiClient(self.configuration))
        if query_type == "alerts":
            alerts = api_instance.list_alerts(query=query)
        else:
            raise NotImplementedError(f"Query type {query_type} not implemented")

        return {
            "alerts": alerts.data,
            "alerts_count": len(alerts.data),
        }


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

    opsgenie_api_key = os.environ.get("OPSGENIE_API_KEY")
    assert opsgenie_api_key

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="OpsGenie Provider",
        authentication={"api_key": opsgenie_api_key},
    )
    provider = OpsgenieProvider(
        context_manager, provider_id="opsgenie-test", config=config
    )
    # provider.notify(
    #    message="Simple alert showing context with name: John Doe",
    #    note="Simple alert",
    #    user="John Doe",
    # )
    provider.query(type="alerts", query="status: open")
