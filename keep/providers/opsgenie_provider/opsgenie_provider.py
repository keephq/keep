import dataclasses
import typing

import json5
import opsgenie_sdk
import pydantic
import requests
from opsgenie_sdk.rest import ApiException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class OpsgenieProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpsGenie api key",
            "hint": "https://support.atlassian.com/opsgenie/docs/create-a-default-api-integration/",
            "sensitive": True,
        },
    )

    # Integration Name is only used for validating scopes
    integration_name: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpsGenie integration name",
            "hint": "https://support.atlassian.com/opsgenie/docs/create-a-default-api-integration/",
        },
    )


class OpsGenieRecipient(pydantic.BaseModel):
    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/Recipient.md
    type: str
    id: typing.Optional[str] = None


class OpsgenieProvider(BaseProvider, ProviderHealthMixin):
    """Create incidents in OpsGenie."""

    PROVIDER_DISPLAY_NAME = "OpsGenie"
    PROVIDER_CATEGORY = ["Incident Management"]

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
        self.configuration.retry_http_response = ["429", "500", "502-599", "404"]
        self.configuration.short_polling_max_retries = 3
        self.configuration.api_key["Authorization"] = self.authentication_config.api_key

    def validate_scopes(self):
        scopes = {}
        self.logger.info("Validating scopes")
        try:
            api_key = "GenieKey " + self.authentication_config.api_key
            url = "https://api.opsgenie.com/v2/"

            # Get the list of integrations
            response = requests.get(
                url + "integrations/",
                headers={"Authorization": api_key},
            )

            if response.status_code != 200:
                response.raise_for_status()

            # Find the OpsGenie integration
            for integration in response.json()["data"]:
                if integration["name"] == self.authentication_config.integration_name:
                    api_key_id = integration["id"]
                    break
            else:
                self.logger.error("Failed to find OpsGenie integration")
                return {
                    "opsgenie:create": f"Failed to find Integration name {self.authentication_config.integration_name}"
                }

            # Get the integration details and check if it has write access
            response = requests.get(
                url + "integrations/" + api_key_id,
                headers={"Authorization": api_key},
            )

            if response.status_code != 200:
                response.raise_for_status()

            if response.json()["data"]["allowWriteAccess"]:
                scopes["opsgenie:create"] = True
            else:
                scopes["opsgenie:create"] = (
                    "OpsGenie integration does not have write access"
                )

        except Exception as e:
            self.logger.exception("Failed to create OpsGenie alert")
            scopes["opsgenie:create"] = str(e)
        return scopes

    def validate_config(self):
        self.authentication_config = OpsgenieProviderAuthConfig(
            **self.config.authentication
        )

    def _delete_alert(self, alert_id: str) -> bool:
        api_instance = opsgenie_sdk.AlertApi(opsgenie_sdk.ApiClient(self.configuration))
        request = api_instance.delete_alert(alert_id)
        response = request.retrieve_result()
        if not response.data.is_success:
            self.logger.error(
                "Failed to delete OpsGenie alert",
                extra={"alert_id": alert_id, "response": response.data.to_dict()},
            )
        return response.data.is_success

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
        if isinstance(tags, str):
            self.logger.debug("Parsing tags", extra={"tags": tags})
            try:
                tags = json5.loads(tags)
                self.logger.debug("Parsed tags", extra={"tags": tags})
            except Exception:
                self.logger.exception("Failed to parse tags")

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
            alert = api_instance.create_alert(create_alert_payload)
            response = alert.retrieve_result()
            if not response.data.is_success:
                raise Exception(
                    f"Failed to create OpsGenie alert: {response.data.status}"
                )
            return response.data.to_dict()
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
        return self._create_alert(
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
