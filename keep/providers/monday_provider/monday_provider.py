"""
MondayProvider is a class that provides a way to create new pulse on Monday.com.
"""

import pydantic
import json
import requests
import dataclasses

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class MondayProviderAuthConfig:
    """
    MondayProviderAuthConfig is a class that holds the authentication information for the MondayProvider.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Personal API Token",
            "sensitive": True,
        },
        default=None,
    )

class MondayProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Monday"
    PROVIDER_CATEGORY = ["Collaboration", "Organizational Tools"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="create_pulse",
            description="Create a new pulse",
        ),
    ]

    url = "https://api.monday.com/v2"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = MondayProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        response = requests.post(
            self.url,
            json={"query": "query { me { id } }"},
            headers=self._get_auth_headers(),
        )

        if response.status_code != 200:
            response.raise_for_status()

        self.logger.info(f"Successfully validated scopes {response.json()}")

        return {"create_pulse": True}

    def _get_auth_headers(self):
        return {
            "Authorization": self.authentication_config.api_token,
        }
        
    def _create_new_pulse(
        self,
        board_id: int,
        group_id: str,
        item_name: str,
        column_values: dict = None,
    ):
        try:
            self.logger.info("Creating new item...")
            headers = self._get_auth_headers()

            query = """
            mutation ($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON) {
                create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) {
                    id
                }
            }
            """

            if column_values is None:
                column_values = {}
            
            column_values = json.dumps({k: v for d in column_values for k, v in d.items()})

            variables = {
                "board_id": board_id,
                "group_id": group_id,
                "item_name": item_name,
                "column_values": column_values
            }

            response = requests.post(self.url, json={"query": query, "variables": variables}, headers=headers)

            self.logger.info(f"Response: {response.json()}")
            self.logger.info(f"Status Code: {response.status_code}")
        
            try:
                if response.status_code != 200:
                    response.raise_for_status()
                self.logger.info("Item created successfully")
                return response.json()
            
            except Exception:
                self.logger.exception("Failed to create item", extra=response.json())
                raise ProviderException(f"Failed to create item: {response.json()}")

        except Exception as e:
            raise ProviderException(f"Failed to create item: {e}")
        
    def _notify(
        self,
        board_id: int,
        group_id: str,
        item_name: str,
        column_values: dict = None,
    ):
        try:
            self.logger.info("Creating new item...")
            self._create_new_pulse(board_id, group_id, item_name, column_values)
        except Exception as e:
            raise ProviderException(f"Failed to create item: {e}")

if __name__ == "__main__":
    pass
