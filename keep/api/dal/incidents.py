import logging
from datetime import timezone, timedelta, datetime
from typing import Optional, List

from pydantic.types import UUID
from sqlalchemy import desc
from sqlmodel import Session, select, col

from keep.api.core.db import engine
from keep.api.models.alert import IncidentDtoIn
from keep.api.models.db.alert import Incident, Alert, AlertToIncident

logger = logging.getLogger(__name__)


def get_last_incidents(
    tenant_id: str, limit: int = 1000, timeframe: int = None
) -> list[Incident]:
    """
    Get the last incidents for each fingerprint along with the first time the.

    Args:
        tenant_id (str): The tenant_id to filter the incidents by.
        limit (int): Amount of objects to return
        timeframe (int|null): Return incidents only for the last <N> days

    Returns:
        List[Incident]: A list of Incident objects.
    """
    with Session(engine) as session:
        query = (
            session.query(
                Incident,
            )
            .filter(Incident.tenant_id == tenant_id)
        )

        if timeframe:
            query = query.filter(
                Incident.start_time
                >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
            )

        # Order by timestamp in descending order and limit the results
        query = query.order_by(desc(Incident.start_time)).limit(limit)
        # Execute the query
        incidents = query.all()

    return incidents


def get_incident_by_fingerprint(tenant_id: str, fingerprint: str) -> Optional[Incident]:
    with Session(engine) as session:
        query = (
            session.query(
                Incident,
            )
            .filter(Incident.tenant_id == tenant_id, Incident.incident_fingerprint == fingerprint)
        )

    return query.first()


def create_incident_from_dto(tenant_id: str, incident_dto: IncidentDtoIn) -> Optional[Incident]:
    with Session(engine) as session:
        new_incident = Incident(
            **incident_dto.dict(),
            tenant_id=tenant_id
        )
        session.add(new_incident)
        session.commit()
        session.refresh(new_incident)
    return new_incident


def update_incident_from_dto_by_fingerprint(
        tenant_id: str,
        fingerprint: str,
        updated_incident_dto: IncidentDtoIn,
) -> Optional[Incident]:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.incident_fingerprint == fingerprint
            )
        ).first()

        if not incident:
            return None

        session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.incident_fingerprint == fingerprint
        ).update({
            "name": updated_incident_dto.name,
            "description": updated_incident_dto.description,
            "assignee": updated_incident_dto.assignee,
        })

        session.commit()
        session.refresh(incident)

        return incident


def delete_incident_by_fingerprint(
        tenant_id: str,
        fingerprint: str,
) -> bool:

    with Session(engine) as session:
        session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.incident_fingerprint == fingerprint
        ).delete()
        session.commit()
        return True


def get_incident_alerts_by_incident_fingerprint(tenant_id: str, fingerprint: str) -> List[Alert]:
    with Session(engine) as session:
        query = (
            session.query(
                Alert,
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .join(Incident, AlertToIncident.incident_id == Incident.id)
            .filter(AlertToIncident.tenant_id == tenant_id, Incident.incident_fingerprint == fingerprint)
        )

    return query.all()


def add_alerts_to_incident_by_incident_fingerprint(
    tenant_id: str,
    fingerprint: str,
    alert_ids: List[UUID]
):
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.incident_fingerprint == fingerprint
            )
        ).first()

        if not incident:
            return None

        existed_alert_ids = session.exec(
            select(AlertToIncident.alert_id).where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
                col(AlertToIncident.alert_id).in_(alert_ids)
            )
        ).all()

        alert_to_incident_entries = [
            AlertToIncident(alert_id=alert_id, incident_id=incident.id, tenant_id=tenant_id)
            for alert_id in alert_ids if alert_id not in existed_alert_ids
        ]

        session.bulk_save_objects(alert_to_incident_entries)
        session.commit()
        return True


def remove_alerts_to_incident_by_incident_fingerprint(
    tenant_id: str,
    fingerprint: str,
    alert_ids: List[UUID]
) -> Optional[int]:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.incident_fingerprint == fingerprint
            )
        ).first()

        if not incident:
            return None

        deleted = (
            session.query(AlertToIncident)
            .where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
                col(AlertToIncident.alert_id).in_(alert_ids)
            )
            .delete()
        )

        session.commit()
        return deleted
