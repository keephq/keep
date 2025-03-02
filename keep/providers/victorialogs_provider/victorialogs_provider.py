"""
VictoriaLogsProvider is a class that allows you to query logs from VictoriaLogs.
"""
import dataclasses

import json
import base64
import pydantic
import typing
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class VictorialogsProviderAuthConfig:
    """
    VictoriaLogsProviderAuthConfig is a class that allows you to authenticate in VictoriaLogs.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "VictoriaLogs Host URL",
            "hint": "e.g. https://victorialogs.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    authentication_type: typing.Literal["NoAuth", "Basic", "Bearer"] = dataclasses.field(
        default=typing.cast(typing.Literal["NoAuth", "Basic", "Bearer"], "NoAuth"),
        metadata={
            "required": True,
            "description": "Authentication Type",
            "type": "select",
            "options": ["NoAuth", "Basic", "Bearer"],
        },
    )

    # Basic Authentication
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

    # Bearer Token
    bearer_token: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Bearer Token",
            "sensitive": True,
            "config_sub_group": "bearer_token",
            "config_main_group": "authentication",
        },
    )

    x_scope_orgid: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "X-Scope-OrgID Header",
            "sensitive": False,
            "config_sub_group": "bearer_token",
            "config_main_group": "authentication",
        },
    )

class VictorialogsProvider(BaseProvider):
    """
    VictoriaLogsProvider is a class that allows
    you to query logs from VictoriaLogs.
    """
    PROVIDER_DISPLAY_NAME = "VictoriaLogs"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="The instance is valid and the user is authenticated",
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
        self.authentication_config = VictorialogsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate the scopes of the provider.
        """
        try:
            url = self._get_url("/")
            response = requests.get(
                url=url,
                headers=self.generate_auth_headers()
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validate scopes")

            return {"authenticated": True}
        
        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": str(e)})
            return {"authenticated": str(e)}

    def _get_url(self, endpoint: str):
        return f"{self.authentication_config.host_url}{endpoint}"
    
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
        
        if self.authentication_config.authentication_type == "Bearer":
            headers = {}
            if self.authentication_config.bearer_token:
                headers["Authorization"] = f"Bearer {self.authentication_config.bearer_token}"
            if self.authentication_config.x_scope_orgid:
                headers["X-Scope-OrgID"] = self.authentication_config.x_scope_orgid
            return headers
    
    def _convert_to_json(self, response: str) -> dict:
        """
        Convert the response string to JSON.
        """
        if "\n" in response:
            log_lines = response.split("\n")
            log_entries = [json.loads(line) for line in log_lines if line.strip()]
        else:
            log_entries = json.loads(response)

        return log_entries
    
    def _query(self, queryType="", query="", time="", start="", end="", step="", account_id="", project_id="", limit="", timeout="", **kwargs: dict) -> dict:
        """
        Query logs from VictoriaLogs.
        """

        if queryType == "query":
            url = self._get_url("/select/logsql/query")
            params = {
                "query": query,
                "limit": limit,
                "timeout": timeout 
            }
            params = {k: v for k, v in params.items() if v}

            headers = self.generate_auth_headers()
            headers.update({
                "AccountID": account_id,
                "ProjectID": project_id
            })
            headers = {k: v for k, v in headers.items() if v}

            response = requests.post(
                url=url,
                data=params,
                headers=headers
            )

            try:
                response.raise_for_status()
                return self._convert_to_json(response.text)
            except Exception as e:
                self.logger.exception("Failed to query logs")
                raise Exception("Could not query logs from VictoriaLogs on /query endpoint: ", str(e))
            
        elif queryType == "hits":
            url = self._get_url("/select/logsql/hits")
            params = {
                "query": query,
                "start": start,
                "end": end,
                "step": step
            }
            params = {k: v for k, v in params.items() if v}

            headers = self.generate_auth_headers()
            headers.update({
                "AccountID": account_id,
                "ProjectID": project_id
            })
            headers = {k: v for k, v in headers.items() if v}

            response = requests.post(
                url=url,
                data=params,
                headers=headers
            )

            try:
                response.raise_for_status()
                return self._convert_to_json(response.text)
            except Exception as e:
                self.logger.exception("Failed to query logs")
                raise Exception("Could not query logs from VictoriaLogs on /hits endpoint: ", str(e))
            
        elif queryType == "stats_query":
            url = self._get_url("/select/logsql/stats_query")
            params = {
                "query": query,
                "time": time
            }
            params = {k: v for k, v in params.items() if v}

            response = requests.post(
                url=url,
                data=params,
                headers=self.generate_auth_headers()
            )

            try:
                response.raise_for_status()
                return self._convert_to_json(response.text)
            except Exception as e:
                self.logger.exception("Failed to query logs")
                raise Exception("Could not query logs from VictoriaLogs on /stats_query endpoint: ", str(e))
            
        elif queryType == "stats_query_range":
            url = self._get_url("/select/logsql/stats_query_range")
            params = {
                "query": query,
                "start": start,
                "end": end,
                "step": step
            }
            params = {k: v for k, v in params.items() if v}

            response = requests.post(
                url=url,
                data=params,
                headers=self.generate_auth_headers()
            )

            try:
                response.raise_for_status()
                return self._convert_to_json(response.text)
            except Exception as e:
                self.logger.exception("Failed to query logs")
                raise Exception("Could not query logs from VictoriaLogs on /stats_query_range endpoint: ", str(e))
            
        else:
            self.logger.exception("Invalid queryType")
            raise Exception("Invalid queryType")
        
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    victorialogs_host_url = os.getenv("VICTORIALOGS_HOST_URL")

    config = ProviderConfig(
        description="VictoriaLogs Provider",
        authentication={
            "host_url": victorialogs_host_url,
        }
    )

    provider = VictorialogsProvider(context_manager, "victorialogs", config)

    logs = provider._query(
        queryType="query",
        query="error"
    )

    print(logs)
