"""
PlannerProvider is a class that provides a way to read data from Microsoft Planner
and create tasks in planner.
"""
import dataclasses
from urllib.parse import urljoin

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class PlannerProviderAuthConfig:
    """Planner authentication configuration."""

    tenant_id: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Tenant ID",
            "sensitive": True,
        },
    )
    client_id: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Client ID",
            "sensitive": True,
        }
    )
    client_secret: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Client Secret",
            "sensitive": True,
        }
    )


class PlannerProvider(BaseProvider):
    """
    Create tasks in Microsoft Planner.
    """
    
    PROVIDER_DISPLAY_NAME = "Microsoft Planner"
    MS_GRAPH_BASE_URL = "https://graph.microsoft.com"
    MS_PLANS_URL = urljoin(base=MS_GRAPH_BASE_URL, url="/v1.0/planner/plans")
    MS_TASKS_URL = urljoin(base=MS_GRAPH_BASE_URL, url="/v1.0/planner/tasks")
    MS_AUTH_BASE_URL = "https://login.microsoftonline.com"
    MS_GRAPH_RESOURCE = "https://graph.microsoft.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.__access_token = self.__generate_access_token()
        self.__headers = {
            "Authorization": f"Bearer {self.__access_token}",
            "Content-Type": "application/json",
        }

    def __generate_access_token(self):
        """
        Helper method to generate the access token.
        """

        MS_TOKEN_URL = urljoin(
            base=self.MS_AUTH_BASE_URL,
            url=f"/{self.authentication_config.tenant_id}/oauth2/token",
        )

        request_body = {
            "grant_type": "client_credentials",
            "client_id": self.authentication_config.client_id,
            "client_secret": self.authentication_config.client_secret,
            "resource": self.MS_GRAPH_RESOURCE,
        }

        self.logger.info("Generating planner access token...")

        response = requests.post(url=MS_TOKEN_URL, data=request_body)

        response.raise_for_status()

        response_data = response.json()

        if "access_token" in response_data:
            self.logger.info("Generated planner access token.")

            return response_data["access_token"]

        return None

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = PlannerProviderAuthConfig(
            **self.config.authentication
        )

    def __get_plan_by_id(self, plan_id=""):
        """
        Helper method to fetch the plan details by id.
        """

        MS_PLAN_URL = f"{self.MS_PLANS_URL}/{plan_id}"

        self.logger.info(f"Fetching plan by id: {plan_id}")

        response = requests.get(url=MS_PLAN_URL, headers=self.__headers)

        # in case of error response
        response.raise_for_status()

        response_data = response.json()

        self.logger.info(f"Fetched plan by id: {plan_id}")

        return response_data

    def __create_task(self, plan_id="", title="", bucket_id=None):
        """
        Helper method to create a task in Planner.
        """

        request_body = {"planId": plan_id, "title": title, "bucketId": bucket_id}

        self.logger.info(f"Creating new task with title: {title}")

        response = requests.post(
            url=self.MS_TASKS_URL, headers=self.__headers, json=request_body
        )

        # in case of error response
        response.raise_for_status()

        response_data = response.json()

        self.logger.info(
            "Created new task with id:%s and title:%s",
            response_data["id"],
            response_data["title"],
        )

        return response_data

    def _notify(self, plan_id="", title="", bucket_id=None, **kwargs: dict):
        # to verify if the plan with plan_id exists or not
        self.__get_plan_by_id(plan_id=plan_id)

        # create a new task in given plan
        created_task = self.__create_task(
            plan_id=plan_id, title=title, bucket_id=bucket_id
        )

        return created_task


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

    planner_client_id = os.environ.get("PLANNER_CLIENT_ID")
    planner_client_secret = os.environ.get("PLANNER_CLIENT_SECRET")
    planner_tenant_id = os.environ.get("PLANNER_TENANT_ID")

    config = {
        "authentication": {
            "client_id": planner_client_id,
            "client_secret": planner_client_secret,
            "tenant_id": planner_tenant_id,
        },
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="planner-keephq",
        provider_type="planner",
        provider_config=config,
    )

    result = provider.notify(plan_id="YOUR_PLANNER_ID", title="Keep HQ Task1")

    print(result)
