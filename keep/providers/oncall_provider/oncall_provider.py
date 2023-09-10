"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
from typing import Literal

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class OncallProviderAuthConfig:
    """
    Grafana authentication configuration.
    """

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Token",
            "hint": "Grafana On-Call API Token",
        },
    )
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana On-Call Host",
            "hint": "E.g. https://keephq.grafana.net",
        },
    )


class GrafanaOncallLabel(pydantic.BaseModel):
    """
    Grafana On-Call label model.
    """

    colorHex: str
    description: str
    label: str


class OncallProvider(BaseProvider):
    """
    Grafana On-Call provider class.
    """

    API_URI = "api/plugins/grafana-incident-app/resources/api/v1"
    provider_description = "Grafana On-Call is a SaaS incident management solution that helps you resolve incidents faster."

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
        self.authentication_config = OncallProviderAuthConfig(
            **self.config.authentication
        )

    def notify(
        self,
        title: str,
        roomPrefix: str = "incident",
        labels: list[GrafanaOncallLabel] = [
            GrafanaOncallLabel(
                colorHex="#ff0000",
                description="Generated with Keep",
                label="keep-generated",
            )
        ],
        isDrill: bool = False,
        severity: Literal["pending", "minor", "major", "critical"] = "minor",
        status: Literal["active", "resolved"] = "active",
        attachCaption: str = None,
        attachURL: str = None,
        incidentID: str = None,
        **kwargs,
    ):
        headers = {
            "Authorization": f"Bearer {self.authentication_config.token}",
            "Content-Type": "application/json",
        }
        if not incidentID:
            payload = {
                "attachCaption": attachCaption,
                "attachURL": attachURL,
                isDrill: isDrill,
                labels: labels,
                roomPrefix: roomPrefix,
                severity: severity,
                status: status,
                title: title,
            }
            response = requests.post(
                url=f"{self.authentication_config.host}/{self.API_URI}/IncidentsService.CreateIncident",
                headers=headers,
                json=payload,
            )
        else:
            payload = {
                "incidentID": incidentID,
                "status": status,
            }
            response = requests.post(
                url=f"{self.authentication_config.host}/{self.API_URI}/IncidentsService.UpdateStatus",
                headers=headers,
                json=payload,
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
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="grafana-oncall-keephq",
        provider_type="oncall",
        provider_config=config,
    )
