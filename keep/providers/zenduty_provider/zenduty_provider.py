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
class ZendutyProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zenduty API Key (Account Token)",
            "sensitive": True,
        }
    )
    integration_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Zenduty Integration Key (for Events API)",
            "sensitive": True,
        },
        default=None,
    )


class ZendutyProvider(
    BaseTopologyProvider, BaseIncidentProvider, ProviderHealthMixin
):
    """Pull alerts and query incidents from Zenduty."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents_read",
            description="Read incidents data.",
            mandatory=True,
            alias="Incidents Data Read",
        ),
        ProviderScope(
            name="services_read",
            description="Read services data for topology.",
            mandatory=False,
            alias="Services Data Read",
        ),
    ]
    BASE_API_URL = "https://www.zenduty.com"
    PROVIDER_DISPLAY_NAME = "Zenduty"
    PROVIDER_CATEGORY = ["Incident Management"]

    # Zenduty Incident Status Mapping
    # 1: Triggered, 2: Acknowledged, 3: Resolved
    INCIDENT_STATUS_MAP = {
        1: IncidentStatus.FIRING,
        2: IncidentStatus.ACKNOWLEDGED,
        3: IncidentStatus.RESOLVED,
    }

    # Zenduty Alert Status Mapping for Keep
    ALERT_STATUS_MAP = {
        1: AlertStatus.FIRING,
        2: AlertStatus.ACKNOWLEDGED,
        3: AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZendutyProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.api_key:
            raise ProviderConfigException(
                "ZendutyProvider requires an api_key",
                provider_id=self.provider_id,
            )

    def __get_headers(self):
        return {
            "Authorization": f"Token {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def _notify(
        self,
        message: str,
        summary: str = "",
        alert_type: str = "critical",
        entity_id: str = "",
        integration_key: str = "",
        **kwargs,
    ):
        """
        Send an event to Zenduty using the Events API.
        """
        routing_key = integration_key or self.authentication_config.integration_key
        if not routing_key:
            raise Exception("Zenduty integration_key is required for notifications")

        url = f"https://events.zenduty.com/api/events/{routing_key}/"
        payload = {
            "message": message,
            "summary": summary or message,
            "alert_type": alert_type,
            "entity_id": entity_id or str(uuid.uuid4()),
            "payload": kwargs,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def _get_all_incidents(self):
        url = f"{self.BASE_API_URL}/api/account/incidents/"
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
        incident_number = event.get("incident_number")
        status = ZendutyProvider.INCIDENT_STATUS_MAP.get(
            event.get("status"), IncidentStatus.FIRING
        )
        
        severity = IncidentSeverity.INFO
        
        created_at_str = event.get("creation_date")
        if created_at_str:
            created_at = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)

        return IncidentDto(
            id=str(incident_number),
            creation_time=created_at,
            user_generated_name=f'ZD-{event.get("title", "unknown")}-{incident_number}',
            status=status,
            severity=severity,
            alert_sources=["zenduty"],
            services=[event.get("service_name", "unknown")],
            is_predicted=False,
            is_candidate=False,
            fingerprint=str(incident_number),
        )

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        """
        Fetch services from Zenduty to build topology.
        """
        url = f"{self.BASE_API_URL}/api/account/services/"
        response = requests.get(url, headers=self.__get_headers())
        response.raise_for_status()
        services = response.json()
        
        topology = []
        for service in services:
            topology.append(
                TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=service["unique_id"],
                    display_name=service["name"],
                    description=service.get("description", ""),
                    team=service.get("team_name", ""),
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
        Format a Zenduty incident/event into a Keep AlertDto.
        """
        incident_number = event.get("incident_number")
        return AlertDto(
            id=str(incident_number),
            name=event.get("title"),
            status=ZendutyProvider.ALERT_STATUS_MAP.get(event.get("status"), AlertStatus.FIRING),
            severity=AlertSeverity.INFO,
            lastReceived=event.get("creation_date"),
            source=["zenduty"],
            original_alert=event,
            fingerprint=str(incident_number),
        )

    def dispose(self):
        pass
