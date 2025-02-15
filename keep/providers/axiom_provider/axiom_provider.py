"""
AxiomProvider is a class that allows to ingest/digest data from Axiom.
"""

import dataclasses
from typing import Optional
from datetime import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class AxiomProviderAuthConfig:
    """
    Axiom authentication configuration.
    """

    api_token: str = dataclasses.field(
        metadata={"required": True, "sensitive": True, "description": "Axiom API Token"}
    )
    organization_id: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": False,
            "description": "Axiom Organization ID",
        },
        default=None,
    )


class AxiomProvider(BaseProvider):
    """Enrich alerts with data from Axiom."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
    💡 For more details on how to configure Axiom to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/axiom-provider).

    To send alerts from Axiom to Keep, Use the following webhook url to configure Axiom send alerts to Keep:

    1. In Axiom, go to the Monitors tab in the Axiom dashboard.
    2. Click on Notifiers in the left sidebar and create a new webhook.
    3. Give it a name and select Custom Webhook as kind of notifier with webhook url as {keep_webhook_api_url}.
    4. Add 'X-API-KEY' as the request header with the value as {api_key}.
    5. Save the webhook.
    6. Go to Monitors tab and click on the Monitors in the left sidebar and create a new monitor.
    7. Create a new monitor and select the notifier created in the previous step as per your requirement. Refer [Axiom Monitors](https://axiom.co/docs/monitor-data/monitors) to create a new monitor.
    8. Save the monitor. Now, you will receive alerts in Keep.
    """

    PROVIDER_DISPLAY_NAME = "Axiom"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Axiom provider.

        """
        self.authentication_config = AxiomProviderAuthConfig(
            **self.config.authentication
        )

    def _query(
        self,
        dataset=None,
        datasets_api_url=None,
        organization_id=None,
        startTime=None,
        endTime=None,
        **kwargs: dict,
    ):
        """
        Query Axiom using the given query

        Args:
            query (str): command to execute

        Returns:
            https://axiom.co/docs/restapi/query#response-example
        """
        datasets_api_url = datasets_api_url or kwargs.get(
            "api_url", "https://api.axiom.co/v1/datasets"
        )
        organization_id = organization_id or self.authentication_config.organization_id
        if not organization_id:
            raise Exception("organization_id is required for Axiom provider")

        if not dataset:
            raise Exception("dataset is required for Axiom provider")

        nocache = kwargs.get("nocache", "true")

        headers = {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "X-Axiom-Org-ID": organization_id,
        }

        # Todo: support easier syntax (e.g. 1d, 1h, 1m, 1s, etc)
        body = {"startTime": startTime, "endTime": endTime}

        # Todo: add support for body parameters (https://axiom.co/docs/restapi/query#request-example)
        response = requests.post(
            f"{datasets_api_url}/{dataset}/query?nocache={nocache}?format=tabular",
            headers=headers,
            json=body,
        )

        # Todo: log response details for better error handling
        return response.json()
    
    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        
        action = event.get("action")
        axiom_event = event.get("event")
        monitorId = axiom_event.get("monitorID")
        body = axiom_event.get("body", "Unable to fetch body")
        description = axiom_event.get("description", "Unable to fetch description")

        queryEndTime = axiom_event.get("queryEndTime")
        queryStartTime = axiom_event.get("queryStartTime")
        timestamp = axiom_event.get("timestamp")
        
        title = axiom_event.get("title", "Unable to fetch title")
        value = axiom_event.get("value", "Unable to fetch value")
        matchedEvent = axiom_event.get("matchedEvent", {})

        def convert_to_iso_format(date_str):
            dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        queryEndTime = convert_to_iso_format(queryEndTime)
        queryStartTime = convert_to_iso_format(queryStartTime)
        timestamp = convert_to_iso_format(timestamp)
        
        alert = AlertDto(
            action=action,
            id=monitorId,
            name=title,
            body=body,
            description=description,
            queryEndTime=queryEndTime,
            queryStartTime=queryStartTime,
            timestamp=timestamp,
            title=title,
            value=value,
            matchedEvent=matchedEvent,
            startedAt=queryStartTime,
            lastReceived=timestamp,
            monitorId=monitorId,
            source=["axiom"],
        )

        return alert

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

    api_token = os.environ.get("AXIOM_API_TOKEN")

    config = {
        "authentication": {"api_token": api_token, "organization_id": "keephq-rxpb"},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="axiom_test",
        provider_type="axiom",
        provider_config=config,
    )
    result = provider.query(dataset="test", startTime="2023-04-26T09:52:04.000Z")
    print(result)
