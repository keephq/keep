import sys, os
import pathlib
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic.types import UUID

from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dto,
    delete_incident_by_id,
    get_incident_alerts_by_incident_id,
    get_incident_by_id,
    get_last_alerts,
    get_last_incidents,
    assign_alert_to_incident,
    remove_alerts_to_incident_by_incident_id,
    update_incident_from_dto_by_id,
)
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.alert import AlertDto, IncidentDto, IncidentDtoIn, IncidentSeverity
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts

router = APIRouter()
logger = logging.getLogger(__name__)

ee_enabled = os.environ.get("EE_ENABLED", "false") == "true"
if ee_enabled:
    path_with_ee = str(pathlib.Path(__file__).parent.resolve()) + "/../../../ee/experimental"
    sys.path.insert(0, path_with_ee)
    from incident_utils import mine_incidents # noqa


@router.post(
    "",
    description="Create new incident",
    status_code=202,
    response_model=IncidentDto,
)
def create_incident_endpoint(
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
    new_incident_dto = IncidentDto.from_db_incident(incident)
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
        incidents_dto.append(
            IncidentDto.from_db_incident(incident)
        )

    logger.info(
        "Fetched incidents from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return incidents_dto


@router.get(
    "/{incident_id}",
    description="Get incident by id",
)
def get_incident(
    incident_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_dto = IncidentDto.from_db_incident(incident)

    return incident_dto


@router.put(
    "/{incident_id}",
    description="Update incident by id",
)
def update_incident(
    incident_id: str,
    updated_incident_dto: IncidentDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )

    incident = update_incident_from_dto_by_id(
        tenant_id, incident_id, updated_incident_dto
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    new_incident_dto = IncidentDto.from_db_incident(incident)

    return new_incident_dto


@router.delete(
    "/{incident_id}",
    description="Delete incident by incident id",
)
def delete_incident(
    incident_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    deleted = delete_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Incident not found")

    return Response(status_code=202)


@router.get(
    "/{incident_id}/alerts",
    description="Get incident alerts by incident incident id",
)
def get_incident_alerts(
    incident_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
) -> List[AlertDto]:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    logger.info(
        "Fetching incident's alert",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    db_alerts = get_incident_alerts_by_incident_id(tenant_id, incident_id)

    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return enriched_alerts_dto


@router.post(
    "/{incident_id}/alerts",
    description="Add alerts to incident",
    status_code=202,
    response_model=List[AlertDto],
)
def add_alerts_to_incident(
    incident_id: str,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    add_alerts_to_incident_by_incident_id(tenant_id, incident_id, alert_ids)

    return Response(status_code=202)


@router.delete(
    "/{incident_id}/alerts",
    description="Delete alerts from incident",
    status_code=202,
    response_model=List[AlertDto],
)
def delete_alerts_from_incident(
    incident_id: str,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:alert"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    remove_alerts_to_incident_by_incident_id(tenant_id, incident_id, alert_ids)

    return Response(status_code=202)

@router.post(
    "/mine",
    description="Create incidents using historical alerts",
)
def mine(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier()),
    use_n_historical_alerts: int = 10000,
    incident_sliding_window_size: int = 6 * 24 * 60 * 60,
    statistic_sliding_window_size: int = 60 * 60,
    jaccard_threshold: float = 0.0,
    fingerprint_threshold: int = 1
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    alerts = get_last_alerts(tenant_id, limit=use_n_historical_alerts)

    if len(alerts) == 0:
        return {"incidents": []}

    incidents = mine_incidents(alerts, incident_sliding_window_size,
                               statistic_sliding_window_size, jaccard_threshold, fingerprint_threshold)
    if len(incidents) == 0:
        return {"incidents": []}
    
    for incident in incidents:
        incident_id = create_incident_from_dto(tenant_id=tenant_id, incident_dto=IncidentDtoIn(
            name="Mined using algorithm", description="Candidate", assignee="none"
        )).id

        for alert in incident['alerts']:
            assign_alert_to_incident(alert.id, incident_id, tenant_id)

    return {"incidents": incidents}
