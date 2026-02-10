"""
CorootProvider is a class that provides a way to read data from Coroot.
"""

import dataclasses
import datetime
import logging
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseProvider,
    BaseTopologyProvider,
    ProviderHealthMixin,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class CorootProviderAuthConfig:
    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Coroot server URL",
            "hint": "http://localhost:8080",
            "validation": "any_http_url",
        }
    )
    api_key: Optional[str] = dataclasses.field(
        metadata={
            "description": "Coroot API Key (optional for Community Edition)",
            "sensitive": True,
        },
        default=None,
    )
    project: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Coroot Project ID",
            "hint": "default",
        },
        default="default",
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class CorootProvider(
    BaseProvider, BaseTopologyProvider, BaseIncidentProvider, ProviderHealthMixin
):
    """Get topology and incidents from Coroot into Keep."""

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_CATEGORY = ["Monitoring", "Observability"]
    PROVIDER_TAGS = ["alert", "topology", "incident"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity", description="Connectivity Test", mandatory=True
        )
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.logger = logging.getLogger(__name__)

    def validate_config(self):
        """
        Validates required configuration for Coroot's provider.
        """
        self.authentication_config = CorootProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {"connectivity": True}
        try:
            self._get_status()
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def _get_status(self):
        headers = {}
        if self.authentication_config.api_key:
            headers["X-API-Key"] = self.authentication_config.api_key

        response = requests.get(
            f"{self.authentication_config.url}/api/project/{self.authentication_config.project}/status",
            headers=headers,
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()
        return response.json()

    def pull_topology(self) -> tuple[List[TopologyServiceInDto], dict]:
        """
        Fetches the service map (topology) from Coroot and transforms it into Keep format.
        """
        headers = {}
        if self.authentication_config.api_key:
            headers["X-API-Key"] = self.authentication_config.api_key

        response = requests.get(
            f"{self.authentication_config.url}/api/project/{self.authentication_config.project}/overview/service-map",
            headers=headers,
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()
        coroot_topology = response.json()

        topology_services = []
        # coroot_topology is likely a list of Applications from renderServiceMap
        for app in coroot_topology:
            app_id = app.get("id", {})
            service_name = app_id.get("name")
            if not service_name:
                continue

            dependencies = {}
            for upstream in app.get("upstreams", []):
                upstream_name = upstream.get("id", {}).get("name")
                if upstream_name:
                    dependencies[upstream_name] = upstream.get("protocol", "unknown")

            topology_service = TopologyServiceInDto(
                service=service_name,
                display_name=service_name,
                source_provider_id=self.provider_id,
                environment=app.get("cluster", "unknown"),
                dependencies=dependencies,
                tags=list(app.get("labels", {}).values()),
            )
            topology_services.append(topology_service)

        return topology_services, {}

    def _get_incidents(self) -> List[IncidentDto]:
        """
        Fetches incidents from Coroot and maps them to Keep Incidents.
        """
        headers = {}
        if self.authentication_config.api_key:
            headers["X-API-Key"] = self.authentication_config.api_key

        response = requests.get(
            f"{self.authentication_config.url}/api/project/{self.authentication_config.project}/incidents",
            headers=headers,
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()
        incidents = response.json()

        incident_dtos = []
        for incident in incidents:
            severity = self.SEVERITIES_MAP.get(
                incident.get("severity"), AlertSeverity.INFO
            )
            incident_dto = IncidentDto(
                id=incident.get("uuid"),
                name=incident.get("name"),
                description=incident.get("summary", ""),
                severity=severity,
                source=["coroot"],
                # Map other fields as needed
            )
            incident_dtos.append(incident_dto)

        return incident_dtos

    def _get_alerts(self) -> List[AlertDto]:
        """
        Fetches incidents from Coroot and maps them to Keep Alerts.
        """
        incidents = self._get_incidents()
        alert_dtos = []
        for incident in incidents:
            alert_dto = AlertDto(
                id=incident.id,
                name=incident.name,
                description=incident.description,
                status=AlertStatus.FIRING,
                severity=incident.severity,
                lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                source=["coroot"],
                payload=incident.dict(),
            )
            alert_dtos.append(alert_dto)
        return alert_dtos

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("Coroot provider does not support notify()")


if __name__ == "__main__":
    # Local testing
    pass
