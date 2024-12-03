"""
Grafana Incident Provider is a class that allows to query all incidents from Grafana Incident.
"""

import dataclasses
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class GrafanaIncidentProviderAuthConfig:
    """
    GrafanaIncidentProviderAuthConfig is a class that allows to authenticate in Grafana Incident.
    """

    host_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana Host URL",
            "sensitive": False,
            "validation": "https_url",
        },
    )

    service_account_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Service Account Token",
            "sensitive": True,
        },
        default=None,
    )


class GrafanaIncidentProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Grafana Incident"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
        ),
    ]
    PROVIDER_CATEGORY = ["Incident Management"]

    SEVERITIES_MAP = {
        "Pending": AlertSeverity.INFO,
        "Critical": AlertSeverity.CRITICAL,
        "Major": AlertSeverity.HIGH,
        "Minor": AlertSeverity.LOW,
    }

    STATUS_MAP = {"active": AlertStatus.FIRING, "resolved": AlertStatus.RESOLVED}

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
        self.authentication_config = GrafanaIncidentProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self):
        """
        Get the headers for the request.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.service_account_token}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "/api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.QueryIncidentPreviews",
                ),
                headers=self.__get_headers(),
                json={
                    "query": {
                        "limit": 10,
                        "orderDirection": "DESC",
                        "orderField": "createdTime",
                    }
                },
            )

            if response.status_code == 200:
                return {"authenticated": True}
            else:
                self.logger.error(f"Failed to validate scopes: {response.status_code}")
                scopes = {
                    "authenticated": f"Unable to query incidents: {response.status_code}"
                }
        except Exception as e:
            self.logger.error(f"Failed to validate scopes: {e}")
            scopes = {"authenticated": f"Unable to query incidents: {e}"}

        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get the alerts from Grafana Incident.
        """
        try:
            response = requests.post(
                urljoin(
                    self.authentication_config.host_url,
                    "/api/plugins/grafana-incident-app/resources/api/v1/IncidentsService.QueryIncidentPreviews",
                ),
                headers=self.__get_headers(),
                json={
                    "query": {
                        "limit": 10,
                        "orderDirection": "DESC",
                        "orderField": "createdTime",
                    }
                },
            )

            if not response.ok:
                self.logger.error(
                    f"Failed to get incidents from grafana incident: {response.status_code}"
                )
                raise Exception(
                    f"Failed to get incidents from grafana incident: {response.status_code} - {response.text}"
                )

            return [
                AlertDto(
                    id=incident["incidentID"],
                    name=incident["title"],
                    status=self.STATUS_MAP[incident["status"]],
                    severity=self.SEVERITIES_MAP[incident["severityLabel"]],
                    lastReceived=incident["modifiedTime"],
                    severityID=incident["severityID"],
                    incidentType=incident["incidentType"],
                    labels=incident["labels"],
                    isDrill=incident["isDrill"],
                    createdTime=incident["createdTime"],
                    modifiedTime=incident["modifiedTime"],
                    closedTime=incident["closedTime"],
                    createdByUser=incident["createdByUser"],
                    title=incident["title"],
                    description=incident["description"],
                    summary=incident["summary"],
                    slug=incident["slug"],
                    incidentStart=incident["incidentStart"],
                    incidentEnd=incident["incidentEnd"],
                    incidentMembershipPreview=incident["incidentMembershipPreview"],
                    fieldValues=incident["fieldValues"],
                    version=incident["version"],
                    source=["grafana_incident"],
                )
                for incident in response.json()["incidentPreviews"]
            ]

        except Exception as e:
            self.logger.error(f"Failed to get incidents from grafana incident: {e}")
            raise Exception(f"Failed to get incidents from grafana incident: {e}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.getenv("GRAFANA_HOST_URL")
    api_token = os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")

    if host_url is None or api_token is None:
        raise Exception(
            "GRAFANA_HOST_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN environment variables are required"
        )

    config = ProviderConfig(
        description="Grafana Incident Provider",
        authentication={
            "host_url": host_url,
            "service_account_token": api_token,
        },
    )

    provider = GrafanaIncidentProvider(
        context_manager,
        provider_id="grafana_incident",
        config=config,
    )

    provider._get_alerts()
