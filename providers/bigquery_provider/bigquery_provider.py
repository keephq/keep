"""
BigQuery provider.
"""

import dataclasses
import json
import os
from typing import Optional

import pydantic
from google.cloud import bigquery

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BigqueryProviderAuthConfig:
    """
    BigQuery authentication configuration.
    """

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The service account JSON with container.viewer role",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": "application/json",
        },
    )
    project_id: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Google Cloud project ID. If not provided, "
            "it will try to fetch it from the environment variable 'GOOGLE_CLOUD_PROJECT'",
        },
    )


class BigqueryProvider(BaseProvider):
    """Enrich alerts with data from BigQuery."""

    provider_id: str
    config: ProviderConfig

    PROVIDER_DISPLAY_NAME = "BigQuery"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Database"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for BigQuery provider.

        """
        if self.config.authentication is None:
            self.config.authentication = {}
        self.authentication_config = BigqueryProviderAuthConfig(
            **self.config.authentication
        )
        # Check for project_id and handle it here.
        if "project_id" not in self.config.authentication:
            try:
                self.config.authentication["project_id"] = os.environ[
                    "GOOGLE_CLOUD_PROJECT"
                ]
            except KeyError:
                raise ValueError(
                    "GOOGLE_CLOUD_PROJECT environment variable is not set."
                )
            if (
                self.config.authentication["project_id"] is None
                or self.config.authentication["project_id"] == ""
            ):
                # If default project not found, raise error
                raise ValueError("BigQuery project id is missing.")

    def init_client(self):
        if self.authentication_config.service_account_json:
            # this is the content of the service account json
            if isinstance(self.authentication_config.service_account_json, dict):
                self.client = bigquery.Client.from_service_account_info(
                    self.authentication_config.service_account_json
                )
            elif isinstance(self.authentication_config.service_account_json, str):
                self.client = bigquery.Client.from_service_account_info(
                    json.loads(self.authentication_config.service_account_json)
                )
            # file? should never happen?
            else:
                self.client = bigquery.Client.from_service_account_json(
                    self.authentication_config.service_account_json
                )
        else:
            self.client = bigquery.Client()
        # check if the project id was set in the environment and use it if exists
        if self.authentication_config.project_id:
            self.client.project = self.authentication_config.project_id
        elif "GOOGLE_CLOUD_PROJECT" in os.environ:
            self.client.project = os.environ["GOOGLE_CLOUD_PROJECT"]
        else:
            raise ValueError(
                "Project ID must be set in either the configuration or the 'GOOGLE_CLOUD_PROJECT' environment variable."
            )

    def dispose(self):
        self.client.close()

    def notify(self, **kwargs):
        pass  # Define how to notify about any alerts or issues

    def _query(self, query: str):
        self.init_client()
        query_job = self.client.query(query)
        results = list(query_job.result())
        return results

    def get_alerts_configuration(self, alert_id: Optional[str] = None):
        pass  # Define how to get alerts from BigQuery if applicable

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        pass  # Define how to deploy an alert to BigQuery if applicable

    @staticmethod
    def get_alert_schema() -> dict:
        pass  # Return alert schema specific to BigQuery

    def get_logs(self, limit: int = 5) -> list:
        pass  # Define how to get logs from BigQuery if applicable

    def expose(self):
        return {}  # Define any parameters to expose


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # If you want to use application default credentials, you can omit the authentication config
    config = {
        # "authentication": {"service_account.json": "/path/to/your/service_account.json"},
        "authentication": {},
    }

    # Create the provider
    provider = BigqueryProvider(
        context_manager,
        provider_id="bigquery-provider",
        provider_type="bigquery",
        config=ProviderConfig(**config),
    )
    # Use the provider to execute a query
    results = provider.query(
        query="""
        SELECT name, SUM(number) as num
        FROM `bigquery-public-data.usa_names.usa_1910_2013`
        WHERE state = 'TX'
        GROUP BY name
        ORDER BY num DESC
        LIMIT 10;
        """
    )

    # Print the results
    for row in results:
        print("{}: {}".format(row.name, row.num))
