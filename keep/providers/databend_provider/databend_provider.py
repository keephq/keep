"""
DatabendProvider is a class that provides a way to interact with Databend.
"""

import os
import base64
import dataclasses

import pydantic
import requests
from urllib.parse import urljoin

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class DatabendProviderAuthConfig:
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Databend host_url",
            "hint": "e.g. https://databend.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Databend username"
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Databend password",
            "sensitive": True
        }
    )

class DatabendProvider(BaseProvider):
    """
    Enrich alerts with data from Databend.
    """

    PROVIDER_DISPLAY_NAME = "Databend"
    PROVIDER_CATEGORY = ["Database"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_server",
            description="The user can connect to the server",
            mandatory=True,
            alias="Connect to the server",
        )
    ]

    def __init__(
            self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.client = None

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            response = requests.post(
                urljoin(self.authentication_config.host_url, "/v1/query"),
                headers=self.generate_auth_headers(),
                json={"sql": "SELECT 1"},
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validated scopes", extra={"response": response.json()})

            return {"connect_to_server": True}

        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": str(e)})
            return {"connect_to_server": str(e)}
    
    def generate_auth_headers(self):
        """
        Generates authentication headers for Databend.
        """
        credentials = f"{self.authentication_config.username}:{self.authentication_config.password}".encode("utf-8")
        encoded_credentials = base64.b64encode(credentials).decode("utf-8")

        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }

    def dispose(self):
        pass
    
    def validate_config(self):
        """
        Validates required configuration fields for Databend provider.
        """
        self.authentication_config = DatabendProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query=""):
      """
      Executes a query on Databend.
      """
      response = requests.post(
          urljoin(self.authentication_config.host_url, "/v1/query"),
          headers=self.generate_auth_headers(),
          json={"sql": query},
      )

      try:
          response.raise_for_status()
          return response.json()
      except Exception as e:
          self.logger.exception("Failed to execute query", extra={"error": str(e)})
          raise Exception("Failed to execute query")

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Databend Provider",
        authentication={
            "host_url": os.environ.get("DATABEND_HOST_URL"),
            "username": os.environ.get("DATABEND_USERNAME"),
            "password": os.environ.get("DATABEND_PASSWORD"),
        }
    )

    databend_provider = DatabendProvider(context_manager, "databend", config)

    result = databend_provider._query("SELECT avg(number) FROM numbers(100000000)")
    print(result)
