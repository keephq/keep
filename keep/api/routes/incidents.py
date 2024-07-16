import logging
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
)
from pydantic.types import UUID

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.dal.incidents import (
    get_last_incidents,
    get_incident_by_fingerprint,
    create_incident_from_dto,
    update_incident_from_dto_by_fingerprint, delete_incident_by_fingerprint,
    get_incident_alerts_by_incident_fingerprint, add_alerts_to_incident_by_incident_fingerprint,
    remove_alerts_to_incident_by_incident_fingerprint
)
from keep.api.models.alert import IncidentDto, IncidentDtoIn, AlertDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    description="Create new incident",
    status_code=202,
    response_model=IncidentDto,
)
def create_incident(
    incident_dto: IncidentDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Creating incidents in DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    incident = create_incident_from_dto(tenant_id, incident_dto)
    new_incident_dto = IncidentDto(**incident.dict())
    logger.info(
        "New incident created in DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return new_incident_dto


@router.get(
    "",
    description="Get last incidents",
)
def get_all_incidents(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> list[IncidentDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incidents from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    incidents = get_last_incidents(tenant_id=tenant_id)

    incidents_dto = []
    for incident in incidents:
        incidents_dto.append(IncidentDto(
            **incident.dict()
        ))

    logger.info(
        "Fetched incidents from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return incidents_dto


@router.get(
    "/{fingerprint}",
    description="Get incident by fingerprint",
)
def get_incident(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_fingerprint(tenant_id=tenant_id, fingerprint=fingerprint)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_dto = IncidentDto(**incident.dict())

    return incident_dto


@router.put(
    "/{fingerprint}",
    description="Update incident by fingerprint",
)
def update_incident(
    fingerprint: str,
    updated_incident_dto: IncidentDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )

    incident = update_incident_from_dto_by_fingerprint(tenant_id, fingerprint, updated_incident_dto)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    new_incident_dto = IncidentDto(**incident.dict())

    return new_incident_dto


@router.delete(
    "/{fingerprint}",
    description="Delete incident by fingerprint",
)
def delete_incident(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"]))
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    deleted = delete_incident_by_fingerprint(tenant_id=tenant_id, fingerprint=fingerprint)
    if not deleted:
        raise HTTPException(status_code=404, detail="Incident not found")

    return Response(status_code=202)

@router.get(
    "/{fingerprint}/alerts",
    description="Get incident alerts by incident fingerprint",
)
def get_incident_alerts(
    fingerprint: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> List[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_fingerprint(tenant_id=tenant_id, fingerprint=fingerprint)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    logger.info(
        "Fetching incident's alert",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_incident_alerts_by_incident_fingerprint(tenant_id, fingerprint)

    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return enriched_alerts_dto


@router.post(
    "/{fingerprint}/alerts",
    description="Add alerts to incident",
    status_code=202,
    response_model=List[AlertDto],
)
def add_alerts_to_incident(
    fingerprint: str,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_fingerprint(tenant_id=tenant_id, fingerprint=fingerprint)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    add_alerts_to_incident_by_incident_fingerprint(tenant_id, fingerprint, alert_ids)

    return Response(status_code=202)


@router.delete(
    "/{fingerprint}/alerts",
    description="Add alerts to incident",
    status_code=202,
    response_model=List[AlertDto],
)
def delete_alerts_from_incident(
    fingerprint: str,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_fingerprint(tenant_id=tenant_id, fingerprint=fingerprint)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    remove_alerts_to_incident_by_incident_fingerprint(
        tenant_id,
        fingerprint,
        alert_ids
    )

    return Response(status_code=202)