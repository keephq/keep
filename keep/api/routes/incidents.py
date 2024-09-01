import asyncio
import logging
import os
import pathlib
import sys
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from pusher import Pusher
from pydantic.types import UUID

from keep.api.arq_pool import get_pool
from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    confirm_predicted_incident_by_id,
    create_incident_from_dto,
    delete_incident_by_id,
    get_incident_alerts_by_incident_id,
    get_incident_by_id,
    get_incident_unique_fingerprint_count,
    get_last_incidents,
    remove_alerts_to_incident_by_incident_id,
    update_incident_from_dto_by_id,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.alert import AlertDto, IncidentDto, IncidentDtoIn
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.import_ee import mine_incidents_and_create_objects
from keep.api.utils.pagination import (
    AlertPaginatedResultsDto,
    IncidentsPaginatedResultsDto,
)
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION = int(
    os.environ.get("MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION", 5)
)

ee_enabled = os.environ.get("EE_ENABLED", "false") == "true"
if ee_enabled:
    path_with_ee = (
        str(pathlib.Path(__file__).parent.resolve()) + "/../../../ee/experimental"
    )
    sys.path.insert(0, path_with_ee)
    from ee.experimental.incident_utils import (  # noqa
        ALGORITHM_VERBOSE_NAME,
        mine_incidents,
    )


def __update_client_on_incident_change(
    pusher_client: Pusher | None, tenant_id: str, incident_id: str | None = None
):
    """
    Update the client on incident change, making the client poll changes.

    Args:
        pusher_client (Pusher | None): Pusher client if pusher is enabled.
        tenant_id (str): Tenant id.
        incident_id (str | None, optional): If this is relevant to a specific incident id. Defaults to None.
            E.g., when someone correlates new alerts to an incident, we want to notify the client that the incident has changed.
    """
    if pusher_client is not None:
        logger.info(
            "Notifying client on incident change",
            extra={"tenant_id": tenant_id, "incident_id": incident_id},
        )
        pusher_client.trigger(
            f"private-{tenant_id}",
            "incident-change",
            {"incident_id": incident_id},
        )
        logger.info(
            "Client notified on incident change",
            extra={"tenant_id": tenant_id, "incident_id": incident_id},
        )
    else:
        logger.debug(
            "Pusher client not available, skipping incident change notification"
        )


@router.post(
    "",
    description="Create new incident",
    status_code=202,
    response_model=IncidentDto,
)
def create_incident_endpoint(
    incident_dto: IncidentDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
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
    __update_client_on_incident_change(pusher_client, tenant_id)
    return new_incident_dto


@router.get(
    "",
    description="Get last incidents",
)
def get_all_incidents(
    confirmed: bool = True,
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> IncidentsPaginatedResultsDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incidents from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    incidents, total_count = get_last_incidents(
        tenant_id=tenant_id,
        is_confirmed=confirmed,
        limit=limit,
        offset=offset,
    )

    incidents_dto = []
    for incident in incidents:
        incidents_dto.append(IncidentDto.from_db_incident(incident))

    logger.info(
        "Fetched incidents from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return IncidentsPaginatedResultsDto(
        limit=limit, offset=offset, count=total_count, items=incidents_dto
    )


@router.get(
    "/{incident_id}",
    description="Get incident by id",
)
def get_incident(
    incident_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
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
    __update_client_on_incident_change(pusher_client, tenant_id)
    return Response(status_code=202)


@router.get(
    "/{incident_id}/alerts",
    description="Get incident alerts by incident incident id",
)
def get_incident_alerts(
    incident_id: str,
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> AlertPaginatedResultsDto:
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
    db_alerts, total_count = get_incident_alerts_by_incident_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )

    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return AlertPaginatedResultsDto(
        limit=limit, offset=offset, count=total_count, items=enriched_alerts_dto
    )


@router.post(
    "/{incident_id}/alerts",
    description="Add alerts to incident",
    status_code=202,
    response_model=List[AlertDto],
)
async def add_alerts_to_incident(
    incident_id: str,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
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
    __update_client_on_incident_change(pusher_client, tenant_id, incident_id)

    fingerprints_count = get_incident_unique_fingerprint_count(tenant_id, incident_id)

    if (
        ee_enabled
        and fingerprints_count > MIN_INCIDENT_ALERTS_FOR_SUMMARY_GENERATION
        and not incident.user_summary
    ):
        pool = await get_pool()
        job = await pool.enqueue_job(
            "process_summary_generation",
            tenant_id=tenant_id,
            incident_id=incident_id,
        )
        logger.info(
            f"Summary generation for incident {incident_id} scheduled, job: {job}",
            extra={
                "algorithm": ALGORITHM_VERBOSE_NAME,
                "tenant_id": tenant_id,
                "incident_id": incident_id,
            },
        )

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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
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
    include_in_schema=False,
)
def mine(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incidents"])
    ),
    alert_lower_timestamp: datetime = None,
    alert_upper_timestamp: datetime = None,
    use_n_historical_alerts: int = 10e10,
    incident_lower_timestamp: datetime = None,
    incident_upper_timestamp: datetime = None,
    use_n_hist_incidents: int = 10e10,
    pmi_threshold: float = 0.0,
    knee_threshold: float = 0.8,
    min_incident_size: int = 5,
    incident_similarity_threshold: float = 0.8,
) -> dict:
    result = asyncio.run(
        mine_incidents_and_create_objects(
            None,
            authenticated_entity.tenant_id,
            alert_lower_timestamp,
            alert_upper_timestamp,
            use_n_historical_alerts,
            incident_lower_timestamp,
            incident_upper_timestamp,
            use_n_hist_incidents,
            pmi_threshold,
            knee_threshold,
            min_incident_size,
            incident_similarity_threshold,
        )
    )
    return result


@router.post(
    "/{incident_id}/confirm",
    description="Confirm predicted incident by id",
)
def confirm_incident(
    incident_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Fetching incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )

    incident = confirm_predicted_incident_by_id(tenant_id, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident candidate not found")

    new_incident_dto = IncidentDto.from_db_incident(incident)

    return new_incident_dto
