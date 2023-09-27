import dataclasses
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class LinearProviderAuthConfig:
    """Linear authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Linear API Token",
            "sensitive": True,
        }
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Linear Project ID",
        }
    )

class LinearProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LinearProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _query(self, **kwargs: dict):
        """
        API for fetching Linear data.

        Args:
            kwargs (dict): Additional parameters for the request.
        """
        self.logger.debug("Fetching data from Linear")

        linear_api_token = self.authentication_config.api_token
        project_id = self.authentication_config.project_id

        # Construct the request URL and headers based on the Linear API documentation
        request_url = f"https://api.linear.app/v1/projects/{project_id}"
        headers = {
            "Authorization": f"Bearer {linear_api_token}",
            "Content-Type": "application/json",
        }

        response = requests.get(request_url, headers=headers)

        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Linear: {response.text}"
            )

        self.logger.debug("Fetched data from Linear")

        linear_data = response.json()
        return {"linear_data": linear_data}

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

    linear_api_token = os.environ.get("LINEAR_API_TOKEN")
    linear_project_id = os.environ.get("LINEAR_PROJECT_ID")

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Linear Input Provider",
        authentication={
            "api_token": linear_api_token,
            "project_id": linear_project_id,
        },
    )
    provider = LinearProvider(context_manager, provider_id="linear", config=config)
    provider.query()  
