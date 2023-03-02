import dataclasses
import datetime
import json
import typing
import uuid

import opsgenie_sdk
import pydantic
from opsgenie_sdk.rest import ApiException

from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OpsgenieProviderAuthConfig:
    api_key: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Ops genie api key (https://support.atlassian.com/opsgenie/docs/api-key-management/)",
        },
        default=None,
    )


class OpsGenieRecipient(pydantic.BaseModel):
    # https://github.com/opsgenie/opsgenie-python-sdk/blob/master/docs/Recipient.md
    type: str
    id: typing.Optional[str] = None


class OpsgenieProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.configuration = opsgenie_sdk.Configuration()
        self.configuration.api_key["Authorization"] = self.authentication_config.api_key

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
            api_response = api_instance.create_alert(create_alert_payload)
            pprint(api_response)
        except ApiException as e:
            self.logger.exception("Failed to create OpsGenie alert")
            raise

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, **kwargs: dict):
        """
        Create a OpsGenie alert.
            Alert/Incident is created either via the Events API or the Incidents API.
            See https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3 for more information

        Args:
            kwargs (dict): The providers with context
        """
        self._create_alert(**kwargs)


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    opsgenie_api_key = os.environ.get("OPSGENIE_API_KEY")
    assert opsgenie_api_key

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="OpsGenie Provider",
        authentication={"api_key": opsgenie_api_key},
    )
    provider = OpsgenieProvider(provider_id="opsgenie-test", config=config)
    provider.notify(
        message="Simple alert showing context with name: {name}".format(
            name="John Doe"
        ),
        note="Simple alert",
        user="John Doe",
    )
