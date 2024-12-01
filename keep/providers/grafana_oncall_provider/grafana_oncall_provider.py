"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import logging
import pydantic
import requests
import dataclasses

from typing import Literal

from urllib.parse import urlparse, urlunparse, urlsplit

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class GrafanaOncallProviderAuthConfig:
    """
    Grafana authentication configuration.
    """

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Token",
            "hint": "Grafana OnCall API Token",
        },
    )
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana OnCall Host",
            "hint": "E.g. https://oncall-prod-us-central-0.grafana.net/oncall/ or http://localhost:8000/",
        },
    )


class GrafanaOncallProvider(BaseProvider):
    """
    Create incidents with Grafana OnCall.
    """

    PROVIDER_DISPLAY_NAME = "Grafana OnCall"
    PROVIDER_CATEGORY = ["Incident Management"]

    API_URI = "api/v1"
    provider_description = "Grafana OnCall is an oncall management solution."

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
        Validates required configuration for Grafana provider.

        """
        self.authentication_config = GrafanaOncallProviderAuthConfig(
            **self.config.authentication
        )


    def clean_url(self, url):
        parsed = urlparse(url)
        normalized_path = '/'.join(part for part in parsed.path.split('/') if part)
        _clean_url = urlunparse(parsed._replace(path=f'/{normalized_path}'))
        return _clean_url


    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        
        super().__init__(context_manager, provider_id, config)
        KEEP_INTEGRATION_NAME = "Keep Integration"

        # if self.config.authentication.get("oncall_integration_link") is not None:
        #     return None

        # Create Grafana OnCall integration if the integration link is not saved
        headers = {
            "Authorization": f"{config.authentication['token']}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(
            url=self.clean_url(f"{config.authentication['host']}/{self.API_URI}/integrations/"),
            headers=headers,
            json={
                "name": KEEP_INTEGRATION_NAME,
                "type":"webhook"
            },
        )
        existing_integration_link = None
        if response.status_code == 400:
            # If integration already exists, get the link
            if response.json().get("detail") == "An integration with this name already exists for this team":
                response = requests.get(
                    url=self.clean_url(f"{config.authentication['host']}/{self.API_URI}/integrations/"),
                    headers=headers,
                )
                response.raise_for_status()
                for integration in response.json()['results']:
                    if integration.get("name") == KEEP_INTEGRATION_NAME:
                        existing_integration_link = integration.get("link")
                        break
        elif response.status_code in [200, 201]:
            response_json = response.json()
            existing_integration_link = response_json.get("link")
        else:
            logger.error(f"Error installing the provider: {response.status_code}")
            raise Exception(f"Error installing the provider: {response.status_code}")
        
        if "integrations/v1/" in urlsplit(existing_integration_link).path:
            self.config.authentication["oncall_integration_link"] = existing_integration_link
        else:
            Exception("Error creating the integration link, the URL is not OnCall formatted.")


    def _notify(
        self,
        title: str,
        alert_uid: str | None = None,
        message: str = "",
        image_url: str = "",
        state: Literal["alerting", "resolved"] = "alerting",
        link_to_upstream_details: str = "",
        **kwargs,
    ):
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=self.config.authentication["oncall_integration_link"],
            headers=headers,
            json={
                "title": title,
                "message": message,
                "alert_uid": alert_uid,
                "image_url": image_url,
                "state": state,
                "link_to_upstream_details": link_to_upstream_details,
            },
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    host = os.environ.get("GRAFANA_ON_CALL_HOST")
    token = os.environ.get("GRAFANA_ON_CALL_TOKEN")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {"host": host, "token": token},
    }
    provider: GrafanaOncallProvider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="grafana-oncall-keephq",
        provider_type="oncall",
        provider_config=config,
    )
    alert = provider.notify("Test Alert")
    print(alert)
