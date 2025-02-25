"""
VictoriaLogsProvider is a class that allows you to query logs from VictoriaLogs.
"""
import dataclasses

import json
import pydantic
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

class VictorialogsProvider(BaseProvider):
    """
    VictoriaLogsProvider is a class that allows
    you to query logs from VictoriaLogs.
    """
    PROVIDER_DISPLAY_NAME = "VictoriaLogs"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="valid_instance",
            description="The instance is valid",
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
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validate scopes")

            return {"valid_instance": True}
        
        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": str(e)})
            return {"valid_instance": str(e)}

    def _get_url(self, endpoint: str):
        return f"{self.authentication_config.host_url}{endpoint}"
    
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

            headers = {
                "AccountID": account_id,
                "ProjectID": project_id
            }
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

            headers = {
                "AccountID": account_id,
                "ProjectID": project_id
            }
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
