"""
Asana Provider is a class that provides a way to create tasks in Asana.
"""

import dataclasses
import typing

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class AsanaProviderAuthConfig:
    """
    Asana Provider Auth Config.
    """
    pat_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Personal Access Token for Asana.",
            "sensitive": True,
            "documentation_url": "https://developers.asana.com/docs/personal-access-token"
        }
    )

class AsanaProvider(BaseProvider):
    """
    Asana Provider is a class that provides a way to create tasks in Asana.
    """

    PROVIDER_CATEGORY = ["Collaboration", "Organizational Tools", "Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to Asana.",
            mandatory=True
        )
    ]

    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "Asana"

    def __init__(
            self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validate the scopes of the provider.
        """

        headers = self._generate_auth_headers()
        url = "https://app.asana.com/api/1.0/projects"

        try:
          response = requests.get(url, headers=headers)

          if response.status_code != 200:
              response.raise_for_status()

          self.logger.info("Successfully validated scopes", extra={"response": response.json()})

          return {"authenticated": True}
        
        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"exception": e})
            return {"authenticated": str(e)}

    def validate_config(self):
        """
        Validate the configuration of the provider.
        """
        self.authentication_config = AsanaProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass
        
    def _generate_auth_headers(self):
        """
        Generate the authentication headers for the provider.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.pat_token}",
            "Accept": "application/json"
        }
    

    def _create_task(
            self,
            name: str,
            projects: typing.List[str],
            **kwargs: dict
    ):
        """
        Create a task in Asana.
        """

        headers = self._generate_auth_headers()
        url = "https://app.asana.com/api/1.0/tasks"

        payload = {
            "data": {
                "projects": projects,
                "name": name,
                **kwargs
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 201:
                response.raise_for_status()

            self.logger.info("Successfully created task", extra={"response": response.json()})

            return response.json()["data"]
        
        except Exception as e:
            self.logger.exception("Failed to create task", extra={"exception": e})
            raise ProviderException(str(e))
        
    def _update_task(
            self,
            task_id: str,
            **kwargs: dict
    ):
        """
        Update a task in Asana.
        """

        headers = self._generate_auth_headers()
        url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

        payload = {
            "data": {
                **kwargs
            }
        }

        try:
            response = requests.put(url, headers=headers, json=payload)

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully updated task", extra={"response": response.json()})

            return response.json()["data"]
        
        except Exception as e:
            self.logger.exception("Failed to update task", extra={"exception": e})
            raise ProviderException(str(e))
        
    def _notify(self, name: str, projects: typing.List[str], **kwargs: dict):
        """
        Create task in Asana.
        """
        return self._create_task(name, projects, **kwargs)
    
    def _query(self, task_id: str, **kwargs: dict):
        """
        Query tasks in Asana.
        """
        return self._update_task(task_id, **kwargs)

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    pat_token = os.getenv("ASANA_PAT_TOKEN")

    config = ProviderConfig(
        description="Asana Provider",
        authentication={
            "pat_token": pat_token
        }
    )

    provider = AsanaProvider(context_manager, "asana_provider", config)

    print(provider._notify("Test Task", ["1234567890"], notes="This is a test task"))