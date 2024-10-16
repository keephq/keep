import asyncio
import logging
import os
import pathlib
import sys
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pusher import Pusher
from pydantic.types import UUID

from keep.api.arq_pool import get_pool
from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    add_audit,
    change_incident_status_by_id,
    confirm_predicted_incident_by_id,
    create_incident_from_dto,
    delete_incident_by_id,
    get_future_incidents_by_incident_id,
    get_incident_alerts_by_incident_id,
    get_incident_by_id,
    get_incident_unique_fingerprint_count,
    get_incidents_meta_for_tenant,
    get_last_incidents,
    get_workflow_executions_for_incident_or_alert,
    remove_alerts_to_incident_by_incident_id,
    update_incident_from_dto_by_id,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import (
    AlertDto,
    EnrichAlertRequestBody,
    IncidentDto,
    IncidentDtoIn,
    IncidentListFilterParamsDto,
    IncidentSeverity,
    IncidentSorting,
    IncidentStatus,
    IncidentStatusChangeDto,
)
from keep.api.models.db.alert import AlertActionType, AlertAudit
from keep.api.routes.alerts import _enrich_alert
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.import_ee import mine_incidents_and_create_objects
from keep.api.utils.pagination import (
    AlertPaginatedResultsDto,
    IncidentsPaginatedResultsDto,
    WorkflowExecutionsPaginatedResultsDto,
)
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.workflowmanager.workflowmanager import WorkflowManager

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
    from ee.experimental.incident_utils import ALGORITHM_VERBOSE_NAME  # noqa


def __update_client_on_incident_change(
    pusher_client: Pusher | None, tenant_id: str, incident_id: UUID | None = None
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
            {"incident_id": str(incident_id)},
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
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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

    try:
        workflow_manager = WorkflowManager.get_instance()
        logger.info("Adding incident to the workflow manager queue")
        workflow_manager.insert_incident(tenant_id, new_incident_dto, "created")
        logger.info("Added incident to the workflow manager queue")
    except Exception:
        logger.exception(
            "Failed to run workflows based on incident",
            extra={"incident_id": new_incident_dto.id, "tenant_id": tenant_id},
        )

    return new_incident_dto


@router.get(
    "/meta",
    description="Get incidents' metadata for filtering",
    response_model=IncidentListFilterParamsDto,
)
def get_incidents_meta(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> IncidentListFilterParamsDto:
    tenant_id = authenticated_entity.tenant_id
    meta = get_incidents_meta_for_tenant(tenant_id=tenant_id)
    return IncidentListFilterParamsDto(**meta)


@router.get(
    "",
    description="Get last incidents",
)
def get_all_incidents(
    confirmed: bool = True,
    limit: int = 25,
    offset: int = 0,
    sorting: IncidentSorting = IncidentSorting.creation_time,
    status: List[IncidentStatus] = Query(None),
    severity: List[IncidentSeverity] = Query(None),
    assignees: List[str] = Query(None),
    sources: List[str] = Query(None),
    affected_services: List[str] = Query(None),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> IncidentsPaginatedResultsDto:
    tenant_id = authenticated_entity.tenant_id

    filters = {}
    if status:
        filters["status"] = [s.value for s in status]
    if severity:
        filters["severity"] = [s.order for s in severity]
    if assignees:
        filters["assignee"] = assignees
    if sources:
        filters["sources"] = sources
    if affected_services:
        filters["affected_services"] = affected_services

    logger.info(
        "Fetching incidents from DB",
        extra={
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "sorting": sorting,
            "filters": filters,
        },
    )

    incidents, total_count = get_last_incidents(
        tenant_id=tenant_id,
        is_confirmed=confirmed,
        limit=limit,
        offset=offset,
        sorting=sorting,
        filters=filters,
    )

    incidents_dto = []
    for incident in incidents:
        incidents_dto.append(IncidentDto.from_db_incident(incident))

    logger.info(
        "Fetched incidents from DB",
        extra={
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "sorting": sorting,
            "filters": filters,
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
    incident_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:incident"])
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
    incident_id: UUID,
    updated_incident_dto: IncidentDtoIn,
    generated_by_ai: bool = Query(
        default=False,
        alias="generatedByAi",
        description="Whether the incident update request was generated by AI",
    ),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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
        tenant_id, incident_id, updated_incident_dto, generated_by_ai
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    new_incident_dto = IncidentDto.from_db_incident(incident)
    try:
        workflow_manager = WorkflowManager.get_instance()
        logger.info("Adding incident to the workflow manager queue")
        workflow_manager.insert_incident(tenant_id, new_incident_dto, "updated")
        logger.info("Added incident to the workflow manager queue")
    except Exception:
        logger.exception(
            "Failed to run workflows based on incident",
            extra={"incident_id": new_incident_dto.id, "tenant_id": tenant_id},
        )
    return new_incident_dto


@router.delete(
    "/{incident_id}",
    description="Delete incident by incident id",
)
def delete_incident(
    incident_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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

    incident_dto = IncidentDto.from_db_incident(incident)

    deleted = delete_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Incident not found")
    __update_client_on_incident_change(pusher_client, tenant_id)
    try:
        workflow_manager = WorkflowManager.get_instance()
        logger.info("Adding incident to the workflow manager queue")
        workflow_manager.insert_incident(tenant_id, incident_dto, "deleted")
        logger.info("Added incident to the workflow manager queue")
    except Exception:
        logger.exception(
            "Failed to run workflows based on incident",
            extra={"incident_id": incident_dto.id, "tenant_id": tenant_id},
        )
    return Response(status_code=202)


@router.get(
    "/{incident_id}/alerts",
    description="Get incident alerts by incident incident id",
)
def get_incident_alerts(
    incident_id: UUID,
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:incidents"])
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


@router.get(
    "/{incident_id}/future_incidents",
    description="Get same incidents linked to this one",
)
def get_future_incidents_for_an_incident(
    incident_id: str,
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:incidents"])
    ),
) -> IncidentsPaginatedResultsDto:
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
        "Fetching future incidents from",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )
    db_incidents, total_count = get_future_incidents_by_incident_id(
        limit=limit,
        offset=offset,
        incident_id=incident_id,
    )
    future_incidents = [
        IncidentDto.from_db_incident(incident) for incident in db_incidents
    ]
    logger.info(
        "Fetched future incidents from DB",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
        },
    )

    return IncidentsPaginatedResultsDto(
        limit=limit, offset=offset, count=total_count, items=future_incidents
    )


@router.get(
    "/{incident_id}/workflows",
    description="Get incident workflows by incident id",
)
def get_incident_workflows(
    incident_id: UUID,
    limit: int = 25,
    offset: int = 0,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:incidents"])
    ),
) -> WorkflowExecutionsPaginatedResultsDto:
    """
    Get all workflows associated with an incident.
    It associated both with the incident itself and alerts associated with the incident.

    """
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching incident's workflows",
        extra={"incident_id": incident_id, "tenant_id": tenant_id},
    )
    workflow_execution_dtos, total_count = (
        get_workflow_executions_for_incident_or_alert(
            tenant_id=tenant_id, incident_id=incident_id, limit=limit, offset=offset
        )
    )

    paginated_workflow_execution_dtos = WorkflowExecutionsPaginatedResultsDto(
        limit=limit, offset=offset, count=total_count, items=workflow_execution_dtos
    )
    return paginated_workflow_execution_dtos


@router.post(
    "/{incident_id}/alerts",
    description="Add alerts to incident",
    status_code=202,
    response_model=List[AlertDto],
)
async def add_alerts_to_incident(
    incident_id: UUID,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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
    try:
        logger.info("Pushing enriched alert to elasticsearch")
        elastic_client = ElasticClient(tenant_id)
        if elastic_client.enabled:
            db_alerts, _ = get_incident_alerts_by_incident_id(
                tenant_id=tenant_id,
                incident_id=incident_id,
                limit=len(alert_ids) + incident.alerts_count,
            )

            enriched_alerts_dto = convert_db_alerts_to_dto_alerts(
                db_alerts, with_incidents=True
            )
            logger.info(
                "Fetched alerts from DB",
                extra={
                    "tenant_id": tenant_id,
                },
            )
            elastic_client.index_alerts(
                alerts=enriched_alerts_dto,
            )
            logger.info("Pushed enriched alert to elasticsearch")
    except Exception:
        logger.exception("Failed to push alert to elasticsearch")
        pass
    __update_client_on_incident_change(pusher_client, tenant_id, incident_id)

    incident_dto = IncidentDto.from_db_incident(incident)

    try:
        workflow_manager = WorkflowManager.get_instance()
        logger.info("Adding incident to the workflow manager queue")
        workflow_manager.insert_incident(tenant_id, incident_dto, "updated")
        logger.info("Added incident to the workflow manager queue")
    except Exception:
        logger.exception(
            "Failed to run workflows based on incident",
            extra={"incident_id": incident_dto.id, "tenant_id": tenant_id},
        )

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
    incident_id: UUID,
    alert_ids: List[UUID],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    alert_lower_timestamp: datetime = None,
    alert_upper_timestamp: datetime = None,
    use_n_historical_alerts: int = None,
    incident_lower_timestamp: datetime = None,
    incident_upper_timestamp: datetime = None,
    use_n_historical_incidents: int = None,
    pmi_threshold: float = None,
    knee_threshold: float = None,
    min_incident_size: int = None,
    incident_similarity_threshold: float = None,
) -> dict:
    result = asyncio.run(
        mine_incidents_and_create_objects(
            ctx=None,
            tenant_id=authenticated_entity.tenant_id,
            alert_lower_timestamp=alert_lower_timestamp,
            alert_upper_timestamp=alert_upper_timestamp,
            use_n_historical_alerts=use_n_historical_alerts,
            incident_lower_timestamp=incident_lower_timestamp,
            incident_upper_timestamp=incident_upper_timestamp,
            use_n_historical_incidents=use_n_historical_incidents,
            pmi_threshold=pmi_threshold,
            knee_threshold=knee_threshold,
            min_incident_size=min_incident_size,
            incident_similarity_threshold=incident_similarity_threshold,
        )
    )
    return result


@router.post(
    "/{incident_id}/confirm",
    description="Confirm predicted incident by id",
    response_model=IncidentDto,
)
def confirm_incident(
    incident_id: UUID,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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


@router.post(
    "/{incident_id}/status",
    description="Change incident status",
    response_model=IncidentDto,
)
def change_incident_status(
    incident_id: UUID,
    change: IncidentStatusChangeDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
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

    with_alerts = change.status == IncidentStatus.RESOLVED
    incident = get_incident_by_id(tenant_id, incident_id, with_alerts=with_alerts)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # We need to do something only if status really changed
    if not change.status == incident.status:
        result = change_incident_status_by_id(tenant_id, incident_id, change.status)
        if not result:
            raise HTTPException(
                status_code=500, detail="Error changing incident status"
            )
        # TODO: same this change to audit table with the comment

        if change.status == IncidentStatus.RESOLVED:
            for alert in incident.alerts:
                _enrich_alert(
                    EnrichAlertRequestBody(
                        enrichments={"status": "resolved"},
                        fingerprint=alert.fingerprint,
                    ),
                    authenticated_entity=authenticated_entity,
                )

        incident.status = change.status

    new_incident_dto = IncidentDto.from_db_incident(incident)

    return new_incident_dto


@router.post("/{incident_id}/comment", description="Add incident audit activity")
def add_comment(
    incident_id: UUID,
    change: IncidentStatusChangeDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher = Depends(get_pusher_client),
) -> AlertAudit:
    extra = {
        "tenant_id": authenticated_entity.tenant_id,
        "commenter": authenticated_entity.email,
        "comment": change.comment,
        "incident_id": str(incident_id),
    }
    logger.info("Adding comment to incident", extra=extra)
    comment = add_audit(
        authenticated_entity.tenant_id,
        str(incident_id),
        authenticated_entity.email,
        AlertActionType.INCIDENT_COMMENT,
        change.comment,
    )

    if pusher_client:
        pusher_client.trigger(
            f"private-{authenticated_entity.tenant_id}", "incident-comment", {}
        )

    logger.info("Added comment to incident", extra=extra)
    return comment
