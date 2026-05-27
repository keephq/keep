import dataclasses
import datetime
import logging
import typing
import uuid

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.models.incident import IncidentDto
from keep.api.models.db.incident import IncidentStatus, IncidentSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseProvider,
    BaseTopologyProvider,
    ProviderHealthMixin,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class PagerTreeProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "PagerTree API Key",
            "sensitive": True,
        }
    )


class PagerTreeProvider(
    BaseTopologyProvider, BaseIncidentProvider, ProviderHealthMixin
):
    """Pull alerts and query incidents from PagerTree."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents_read",
            description="Read incidents data.",
            mandatory=True,
            alias="Incidents Data Read",
        ),
        ProviderScope(
            name="services_read",
            description="Read teams data for topology.",
            mandatory=False,
            alias="Teams Data Read",
        ),
    ]
    BASE_API_URL = "https://api.pagertree.com/api/v4"
    PROVIDER_DISPLAY_NAME = "PagerTree"
    PROVIDER_CATEGORY = ["Incident Management"]

    # PagerTree Incident Status Mapping
    # open, acknowledged, resolved
    INCIDENT_STATUS_MAP = {
        "open": IncidentStatus.FIRING,
        "acknowledged": IncidentStatus.ACKNOWLEDGED,
        "resolved": IncidentStatus.RESOLVED,
    }

    # PagerTree Alert Status Mapping for Keep
    ALERT_STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PagerTreeProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.api_key:
            raise ProviderConfigException(
                "PagerTreeProvider requires an api_key",
                provider_id=self.provider_id,
            )

    def __get_headers(self):
        return {
            "x-api-key": self.authentication_config.api_key,
            "Content-Type": "application/json",
        }

    def _notify(
        self,
        title: str,
        urgency: str = "high",
        description: str = "",
        destinations: list = None,
        **kwargs,
    ):
        """
        Send an alert to PagerTree.
        """
        url = f"{self.BASE_API_URL}/alerts"
        payload = {
            "title": title,
            "urgency": urgency,
            "description": description or title,
            "destination_team_ids": destinations or [],
            "meta": {
                "incident": True,
                "incident_severity": "SEV-2",
                "incident_message": title
            }
        }
        response = requests.post(url, json=payload, headers=self.__get_headers())
        response.raise_for_status()
        return response.json()

    def _get_all_incidents(self):
        url = f"{self.BASE_API_URL}/incidents"
        response = requests.get(url, headers=self.__get_headers())
        response.raise_for_status()
        return response.json()

    def _get_incidents(self) -> list[IncidentDto]:
        raw_incidents = self._get_all_incidents()
        incidents = []
        for incident in raw_incidents:
            incidents.append(self._format_incident(incident))
        return incidents

    @staticmethod
    def _format_incident(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> IncidentDto:
        incident_id = event.get("id")
        status = PagerTreeProvider.INCIDENT_STATUS_MAP.get(
            event.get("status"), IncidentStatus.FIRING
        )
        
        severity_map = {
            "SEV-1": IncidentSeverity.CRITICAL,
            "SEV-2": IncidentSeverity.HIGH,
            "SEV-3": IncidentSeverity.MEDIUM,
            "SEV-4": IncidentSeverity.LOW,
            "SEV-5": IncidentSeverity.INFO,
        }
        severity = severity_map.get(event.get("severity"), IncidentSeverity.INFO)
        
        created_at_str = event.get("created_at")
        if created_at_str:
            created_at = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)

        return IncidentDto(
            id=str(incident_id),
            creation_time=created_at,
            user_generated_name=f'PT-{event.get("title", "unknown")}-{incident_id}',
            status=status,
            severity=severity,
            alert_sources=["pagertree"],
            services=[event.get("team_name", "unknown")],
            is_predicted=False,
            is_candidate=False,
            fingerprint=str(incident_id),
        )

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        """
        Fetch teams from PagerTree to build topology.
        """
        url = f"{self.BASE_API_URL}/teams"
        response = requests.get(url, headers=self.__get_headers())
        response.raise_for_status()
        teams = response.json()
        
        topology = []
        for team in teams:
            topology.append(
                TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=team["id"],
                    display_name=team["name"],
                    description=team.get("description", ""),
                    team=team["name"],
                )
            )
        return topology, {}

    def get_alerts(self) -> list[AlertDto]:
        raw_incidents = self._get_all_incidents()
        alerts = []
        for incident in raw_incidents:
            alerts.append(self._format_alert(incident))
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a PagerTree incident into a Keep AlertDto.
        """
        incident_id = event.get("id")
        
        severity_map = {
            "SEV-1": AlertSeverity.CRITICAL,
            "SEV-2": AlertSeverity.HIGH,
            "SEV-3": AlertSeverity.WARNING,
            "SEV-4": AlertSeverity.INFO,
            "SEV-5": AlertSeverity.INFO,
        }
        severity = severity_map.get(event.get("severity"), AlertSeverity.INFO)

        return AlertDto(
            id=str(incident_id),
            name=event.get("title"),
            status=PagerTreeProvider.ALERT_STATUS_MAP.get(event.get("status"), AlertStatus.FIRING),
            severity=severity,
            lastReceived=event.get("created_at"),
            source=["pagertree"],
            original_alert=event,
            fingerprint=str(incident_id),
        )

    def dispose(self):
        pass
