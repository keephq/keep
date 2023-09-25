import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class PlannerProviderAuthConfig:
    """Planner authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Microsoft Planner API Token",
            "sensitive": True,
        }
    )

class PlannerProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PlannerProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _query(self, plan_id="", **kwargs: dict):
        """
        API for fetching Microsoft Planner data.

        Args:
            kwargs (dict): Additional parameters for the request.
        """
        self.logger.debug("Fetching data from Microsoft Planner")

        planner_api_token = self.authentication_config.api_token

        # Construct the request URL and headers based on the Microsoft Planner API documentation
        request_url = f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}/tasks"
        headers = {
            "Authorization": f"Bearer {planner_api_token}",
            "Content-Type": "application/json",
        }

        response = requests.get(request_url, headers=headers)

        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Microsoft Planner: {response.text}"
            )

        self.logger.debug("Fetched data from Microsoft Planner")

        planner_data = response.json()
        return {"planner_data": planner_data}

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

    planner_api_token = os.environ.get("PLANNER_API_TOKEN")

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Microsoft Planner Input Provider",
        authentication={"api_token": planner_api_token},
    )
    provider = PlannerProvider(context_manager, provider_id="planner", config=config)
    provider.query(plan_id="planner-plan-id")
