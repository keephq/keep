"""
PlannerProvider is a class that provides a way to read data from Microsoft Planner
and create tasks in planner.
"""
import dataclasses

import pydantic
import requests
from azure.identity import ClientSecretCredential
from urllib.parse import urljoin

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class PlannerProviderAuthConfig:
    """Planner authentication configuration."""

    PLANNER_DEFAULT_SCOPE = 'https://graph.microsoft.com/.default'

    tenant_id: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Tenant ID", "sensitive": True
        },
    )
    client_id: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Client ID", "sensitive": True
        }
    )
    client_secret: str | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Planner Client Secret", "sensitive": True
        }
    )
    scopes: list = dataclasses.field(default_factory=[PLANNER_DEFAULT_SCOPE])


class PlannerProvider(BaseProvider):
    """
    Microsoft Planner provider class.
    """
    MS_GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'
    MS_PLANS_URL = urljoin(base=MS_GRAPH_BASE_URL, url="planner/plans")
    MS_TASKS_URL = urljoin(base=MS_GRAPH_BASE_URL, url="planner/tasks")

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.access_token = self.__generate_access_token()
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def __generate_access_token(self):
        credential = ClientSecretCredential(
            self.authentication_config.tenant_id,
            self.authentication_config.client_id,
            self.authentication_config.client_secret
        )
        access_token = credential.get_token(
            scopes=self.authentication_config.scopes
        ).token

        return access_token

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = PlannerProviderAuthConfig(
            **self.config.authentication
        )

    def __get_plan_by_id(self,  plan_id=""):
        """
        Helper method to fetch the plan details by id.
        """

        MS_PLAN_URL = f"{self.MS_PLANS_URL}/{plan_id}"

        self.logger.info(f"Fetching plan by id: {plan_id}")

        response = requests.get(
            url=MS_PLAN_URL,
            headers=self.headers
        )

        # in case of error response
        response.raise_for_status()

        response_data = response.json()

        self.logger.info(f"Fetched plan by id: {plan_id}")

        return response_data

    def __create_task(self, plan_id="", title="", bucket_id=None):
        """
        Helper method to create a task in Planner.
        """

        request_body = {
            "planId": plan_id,
            "title": title,
            "bucketId": bucket_id
        }

        self.logger.info(f"Creating new task with title: {title}")

        response = requests.post(
            url=self.MS_TASKS_URL,
            header=self.headers,
            json=request_body
        )

        # in case of error response
        response.raise_for_status()

        response_data = response.json()

        self.logger.info(
            f"Created new task with id:{response_data.id} and title:{response_data.title}"
        )

        return response_data

    def notify(
        self,
        plan_id="",
        title="",
        bucket_id=None,
        **kwargs: dict
    ):
        # to verify if the plan with plan_id exists or not
        plan = self.__get_plan_by_id(plan_id=plan_id)

        # create a new task in given plan
        created_task = self.__create_task(
            plan_id=plan_id,
            title=title,
            bucket_id=bucket_id
        )

        return created_task


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler()]
    )
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
            "tenant_id": planner_tenant_id
        },
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="planner-keephq",
        provider_type="planner",
        provider_config=config,
    )

    result = provider.notify(
        plan_id="YOUR_PLANNER_ID",
        title="Keep HQ Task1"
    )

    print(result)
