import logging
from typing import List, Optional
from uuid import UUID

from pusher import Pusher
from sqlmodel import Session

from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dto,
    get_incident_alerts_by_incident_id,
)
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import IncidentDto, IncidentDtoIn
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.workflowmanager.workflowmanager import WorkflowManager


class IncidentBl:
    def __init__(
        self, tenant_id: str, session: Session, pusher_client: Optional[Pusher] = None
    ):
        self.tenant_id = tenant_id
        self.session = session
        self.pusher_client = pusher_client
        self.logger = logging.getLogger(__name__)

    def create_incident(self, incident_dto: IncidentDtoIn) -> IncidentDto:
        incident = create_incident_from_dto(self.tenant_id, incident_dto)
        new_incident_dto = IncidentDto.from_db_incident(incident)
        self.__update_client_on_incident_change()
        self.__run_workflows(new_incident_dto, "created")
        return new_incident_dto

    def add_alerts_to_incident(self, incident_id: UUID, alert_ids: List[UUID]) -> None:
        add_alerts_to_incident_by_incident_id(self.tenant_id, incident_id, alert_ids)
        self.__update_elastic(incident_id, alert_ids)
        self.__update_client_on_incident_change(incident_id)

    def __update_elastic(self, incident_id: UUID, alert_ids: List[UUID]):
        try:
            elastic_client = ElasticClient(self.tenant_id)
            if elastic_client.enabled:
                db_alerts, _ = get_incident_alerts_by_incident_id(
                    tenant_id=self.tenant_id,
                    incident_id=incident_id,
                    limit=len(alert_ids),
                )
                enriched_alerts_dto = convert_db_alerts_to_dto_alerts(
                    db_alerts, with_incidents=True
                )
                elastic_client.index_alerts(alerts=enriched_alerts_dto)
        except Exception:
            self.logger.exception("Failed to push alert to elasticsearch")

    def __update_client_on_incident_change(self, incident_id: Optional[UUID] = None):
        if self.pusher_client is not None:
            self.pusher_client.trigger(
                f"private-{self.tenant_id}",
                "incident-change",
                {"incident_id": str(incident_id) if incident_id else None},
            )

    def __run_workflows(self, incident_dto: IncidentDto, action: str):
        try:
            workflow_manager = WorkflowManager.get_instance()
            workflow_manager.insert_incident(self.tenant_id, incident_dto, action)
        except Exception:
            self.logger.exception(
                "Failed to run workflows based on incident",
                extra={"incident_id": incident_dto.id, "tenant_id": self.tenant_id},
            )
