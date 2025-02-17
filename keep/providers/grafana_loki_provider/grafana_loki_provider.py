"""
GrafanaLokiProvider is a class that allows you to query logs from Grafana Loki.
"""

import typing
import base64
import dataclasses
from urllib.parse import urljoin

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GrafanaLokiProviderAuthConfig:
    """
    GrafanaLokiProviderAuthConfig is a class that allows you to authenticate in Grafana Loki.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana Loki Host URL",
            "hint": "e.g. https://keephq.grafana.net",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    authentication_type: typing.Literal["NoAuth", "Basic", "X-Scope-OrgID"] = dataclasses.field(
        default=typing.Literal["NoAuth"],
        metadata={
            "required": True,
            "description": "Authentication Type",
            "type": "select",
            "options": ["NoAuth", "Basic", "X-Scope-OrgID"],
        },
    )

    username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "HTTP basic authentication - Username",
            "sensitive": False,
            "config_sub_group": "basic_authentication",
            "config_main_group": "authentication",
        },
    )

    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "HTTP basic authentication - Password",
            "sensitive": True,
            "config_sub_group": "basic_authentication",
            "config_main_group": "authentication",
        },
    )

    x_scope_orgid: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "X-Scope-OrgID Header Authentication",
            "sensitive": False,
            "config_sub_group": "x_scope_orgid",
            "config_main_group": "authentication",
        },
    )

class GrafanaLokiProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Grafana Loki"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Instance is valid and user is authenticated",
        ),
    ]

    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(
            self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass
    
    def validate_config(self):
        """
        Validate the configuration of the provider.
        """
        self.authentication_config = GrafanaLokiProviderAuthConfig(
            **self.config.authentication
        )

    def generate_auth_headers(self):
        """
        Generate the authentication headers.
        """
        if self.authentication_config.authentication_type == "Basic":
            credentials = f"{self.authentication_config.username}:{self.authentication_config.password}".encode("utf-8")
            encoded_credentials = base64.b64encode(credentials).decode("utf-8")
            return {
                "Authorization": f"Basic {encoded_credentials}"
            }
        
        if self.authentication_config.authentication_type == "X-Scope-OrgID":
            return {
                "X-Scope-OrgID": self.authentication_config.x_scope_orgid
            }
        
        return {}

    def validate_scopes(self):
        """
        Validate the scopes of the provider.
        """
        try:
            response = requests.get(
                urljoin(self.authentication_config.host_url, "/loki/api/v1/status/buildinfo"),
                headers=self.generate_auth_headers(),
                timeout=5,
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validated scopes", extra={"response": response.json()})

            return {"authenticated": True}
        
        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": e})
            return {"authenticated": str(e)}
        
    def _query(self, query="", limit="", time="", direction="", start="", end="", since="", step="", interval="", queryType="", **kwargs: dict):
        """
        Query logs from Grafana Loki.
        """
        if queryType == "query":
            params = {
              "query": query,
              "limit": limit,
              "time": time,
              "direction": direction,
            }

            params = {k: v for k, v in params.items() if v}

            response = requests.get(
              f"{self.authentication_config.host_url}/loki/api/v1/query",
              headers=self.generate_auth_headers(),
              params=params
            )

            try:
                response.raise_for_status()
                return response.json()
            except Exception as e:
                self.logger.error("Failed to query logs from Grafana Loki", extra={"error": e})
                raise Exception("Could not query logs from Grafana Loki with query")
            
        elif queryType == "query_range":
            params = {
              "query": query,
              "limit": limit,
              "start": start,
              "end": end,
              "since": since,
              "step": step,
              "interval": interval,
              "direction": direction,
            }
            
            params = {k: v for k, v in params.items() if v}

            response = requests.get(
              f"{self.authentication_config.host_url}/loki/api/v1/query_range",
              headers=self.generate_auth_headers(),
              params=params
            )

            try:
                response.raise_for_status()
                return response.json()
            
            except Exception as e:
                self.logger.error("Failed to query logs from Grafana Loki", extra={"error": e})
                raise Exception("Could not query logs from Grafana Loki with query_range")
            
        else:
            self.logger.error("Invalid query type")
            raise Exception("Invalid query type")
        
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    grafana_loki_host_url = os.getenv("GRAFANA_LOKI_HOST_URL")

    config = ProviderConfig(
        description="Grafana Loki Provider",
        authentication={
            "hostUrl": grafana_loki_host_url,
        }
    )

    provider = GrafanaLokiProvider(context_manager, "grafana_loki", config)

    logs = provider._query(
        query='sum(rate({job="varlogs"}[5m])) by (level)'
    )
    print(logs)
