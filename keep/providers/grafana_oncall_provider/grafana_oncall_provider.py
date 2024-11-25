"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import random
from typing import Literal

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


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
            "hint": "E.g. https://keephq.grafana.net",
        },
    )


class GrafanaOncallProvider(BaseProvider):
    """
    Create incidents with Grafana OnCall.
    """

    PROVIDER_DISPLAY_NAME = "Grafana OnCall"
    PROVIDER_CATEGORY = ["Incident Management"]

    API_URI = "api/plugins/grafana-incident-app/resources/api"
    provider_description = "Grafana OnCall is a SaaS incident management solution that helps you resolve incidents faster."

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

    @staticmethod
    def random_color() -> str:
        return random.randint(0, 255)

    def _notify(
        self,
        title: str,
        roomPrefix: str = "incident",
        labels: list[str] = ["keep-generated"],
        isDrill: bool = False,
        severity: Literal["pending", "minor", "major", "critical"] = "minor",
        status: Literal["active", "resolved"] = "active",
        attachCaption: str = "",
        attachURL: str = "",
        incidentID: str = "",
        **kwargs,
    ):
        headers = {
            "Authorization": f"Bearer {self.authentication_config.token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=f"{self.authentication_config.host}/{self.API_URI}/OrgService.GetOrg",
            headers=headers,
            json={},
        )
        response.raise_for_status()
        response = response.json()
        existing_labels = [
            label.get("label")
            for label in response.get("org", {}).get("incidentLabels", [])
        ]
        if not incidentID:
            self.logger.info(f'Creating incident "{title}"')
            labels_obj = []
            for label in labels:
                if label not in existing_labels:
                    response = requests.post(
                        url=f"{self.authentication_config.host}/{self.API_URI}/OrgService.AddIncidentLabel",
                        headers=headers,
                        json={
                            "incidentLabel": {
                                "label": label,
                                "colorHex": "#%02X%02X%02X"
                                % (
                                    self.random_color(),
                                    self.random_color(),
                                    self.random_color(),
                                ),
                                "description": label,
                            }
                        },
                    )
                labels_obj.append({"label": label})
            payload = {
                "attachCaption": attachCaption,
                "attachURL": attachURL,
                "isDrill": isDrill,
                "labels": labels_obj,
                "roomPrefix": roomPrefix,
                "severity": severity,
                "status": status,
                "title": title,
            }
            response = requests.post(
                url=f"{self.authentication_config.host}/{self.API_URI}/v1/IncidentsService.CreateIncident",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            self.logger.info(f'Created incident "{title}"')
        else:
            self.logger.info(f'Updating incident status for incident "{incidentID}"')
            payload = {
                "incidentID": incidentID,
                "status": status,
            }
            response = requests.post(
                url=f"{self.authentication_config.host}/{self.API_URI}/v1/IncidentsService.UpdateStatus",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            self.logger.info(f'Updated incident status for incident "{incidentID}"')
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
    incident = provider.notify("Test Incident")
    print(incident)
