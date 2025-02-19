import logging
from datetime import datetime
from typing import List, Optional

from arq import ArqRedis
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pusher import Pusher
from pydantic.types import UUID
from sqlmodel import Session

from keep.api.arq_pool import get_pool
from keep.api.bl.ai_suggestion_bl import AISuggestionBl
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.bl.incidents_bl import IncidentBl
from keep.api.consts import KEEP_ARQ_QUEUE_BASIC, REDIS
from keep.api.core.cel_to_sql.sql_providers.base import CelToSqlException
from keep.api.core.db import (
    DestinationIncidentNotFound,
    add_audit,
    change_incident_status_by_id,
    confirm_predicted_incident_by_id,
    get_future_incidents_by_incident_id,
    get_incident_alerts_and_links_by_incident_id,
    get_incident_by_id,
    get_incidents_meta_for_tenant,
    get_last_alerts,
    get_rule,
    get_session,
    get_workflow_executions_for_incident_or_alert,
    merge_incidents_to_id,
)
from keep.api.core.dependencies import extract_generic_body, get_pusher_client
from keep.api.core.incidents import (
    get_incident_facets,
    get_incident_facets_data,
    get_incident_potential_facet_fields,
    get_last_incidents_by_cel,
)
from keep.api.models.alert import (
    AlertDto,
    EnrichAlertRequestBody,
    EnrichIncidentRequestBody,
    IncidentCommit,
    IncidentDto,
    IncidentDtoIn,
    IncidentListFilterParamsDto,
    IncidentsClusteringSuggestion,
    IncidentSeverity,
    IncidentSeverityChangeDto,
    IncidentSorting,
    IncidentStatus,
    IncidentStatusChangeDto,
    MergeIncidentsRequestDto,
    MergeIncidentsResponseDto,
    SplitIncidentRequestDto,
    SplitIncidentResponseDto,
)
from keep.api.models.db.alert import ActionType, AlertAudit
from keep.api.models.facet import FacetOptionsQueryDto
from keep.api.models.workflow import WorkflowExecutionDTO
from keep.api.routes.alerts import _enrich_alert
from keep.api.tasks.process_incident_task import process_incident
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.pagination import (
    AlertWithIncidentLinkMetadataPaginatedResultsDto,
    IncidentsPaginatedResultsDto,
    WorkflowExecutionsPaginatedResultsDto,
)
from keep.api.utils.pluralize import pluralize
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.providers_factory import ProvidersFactory
from keep.topologies.topologies_service import TopologiesService  # noqa

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
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
    session: Session = Depends(get_session),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    return incident_bl.create_incident(incident_dto)


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
    predicted: Optional[bool] = None,
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
    cel: str = Query(None),
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

    # get all preset ids that the user has access to
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    # Note: if no limitations (allowed_preset_ids is []), then all presets are allowed
    allowed_incident_ids = identity_manager.get_user_permission_on_resource_type(
        resource_type="incident",
        authenticated_entity=authenticated_entity,
    )

    try:
        incidents, total_count = get_last_incidents_by_cel(
            tenant_id=tenant_id,
            is_confirmed=confirmed,
            is_predicted=predicted,
            limit=limit,
            offset=offset,
            sorting=sorting,
            cel=cel,
            allowed_incident_ids=allowed_incident_ids,
        )
    except CelToSqlException as e:
        logger.exception(f'Error parsing CEL expression "{cel}". {str(e)}')
        raise HTTPException(
            status_code=400, detail=f"Error parsing CEL expression: {cel}"
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


@router.post(
    "/facets/options",
    description="Query incident facet options. Accepts dictionary where key is facet id and value is cel to query facet",
)
def fetch_inicident_facet_options(
    facet_options_query: FacetOptionsQueryDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching incident facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    # get all preset ids that the user has access to
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    # Note: if no limitations (allowed_preset_ids is []), then all presets are allowed
    allowed_incident_ids = identity_manager.get_user_permission_on_resource_type(
        resource_type="incident",
        authenticated_entity=authenticated_entity,
    )

    facet_options = get_incident_facets_data(
        tenant_id=tenant_id,
        allowed_incident_ids=allowed_incident_ids,
        facet_options_query=facet_options_query,
    )

    logger.info(
        "Fetched incident facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facet_options


@router.get(
    "/facets",
    description="Get incident facets",
)
def fetch_inicident_facets(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching incident facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    facets = get_incident_facets(tenant_id=tenant_id)

    logger.info(
        "Fetched incident facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facets


@router.get(
    "/facets/fields",
    description="Get potential fields for incident facets",
)
def fetch_alert_facet_fields(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:alert"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching incident facet fields from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    fields = get_incident_potential_facet_fields(tenant_id=tenant_id)

    logger.info(
        "Fetched incident facet fields from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )
    return fields


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

    rule = None
    if incident.rule_id:
        rule = get_rule(tenant_id, incident.rule_id)

    incident_dto = IncidentDto.from_db_incident(incident, rule)

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
    pusher_client: Pusher | None = Depends(get_pusher_client),
    session: Session = Depends(get_session),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session=session, pusher_client=pusher_client)
    new_incident_dto = incident_bl.update_incident(
        incident_id, updated_incident_dto, generated_by_ai
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
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    incident_bl.delete_incident(incident_id)
    return Response(status_code=202)


@router.post(
    "/{incident_id}/split",
    description="Split incident by incident id",
    response_model=SplitIncidentResponseDto,
)
async def split_incident(
    incident_id: UUID,
    command: SplitIncidentRequestDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
    session: Session = Depends(get_session),
) -> SplitIncidentResponseDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Splitting incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
            "alert_fingerprints": command.alert_fingerprints,
        },
    )
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    await incident_bl.add_alerts_to_incident(
        incident_id=command.destination_incident_id,
        alert_fingerprints=command.alert_fingerprints,
    )
    incident_bl.delete_alerts_from_incident(
        incident_id=incident_id, alert_fingerprints=command.alert_fingerprints
    )
    return SplitIncidentResponseDto(
        destination_incident_id=command.destination_incident_id,
        moved_alert_fingerprints=command.alert_fingerprints,
    )


@router.post(
    "/merge", description="Merge incidents", response_model=MergeIncidentsResponseDto
)
def merge_incidents(
    command: MergeIncidentsRequestDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
) -> MergeIncidentsResponseDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Merging incidents",
        extra={
            "source_incident_ids": command.source_incident_ids,
            "destination_incident_id": command.destination_incident_id,
            "tenant_id": tenant_id,
        },
    )

    try:
        merged_ids, skipped_ids, failed_ids = merge_incidents_to_id(
            tenant_id,
            command.source_incident_ids,
            command.destination_incident_id,
            authenticated_entity.email,
        )

        if not merged_ids:
            message = "No incidents merged"
        else:
            message = f"{pluralize(len(merged_ids), 'incident')} merged into {command.destination_incident_id} successfully"

        if skipped_ids:
            message += f", {pluralize(len(skipped_ids), 'incident')} were skipped"
        if failed_ids:
            message += f", {pluralize(len(failed_ids), 'incident')} failed to merge"

        return MergeIncidentsResponseDto(
            merged_incident_ids=merged_ids,
            skipped_incident_ids=skipped_ids,
            failed_incident_ids=failed_ids,
            destination_incident_id=command.destination_incident_id,
            message=message,
        )
    except DestinationIncidentNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{incident_id}/alerts",
    description="Get incident alerts by incident incident id",
)
def get_incident_alerts(
    incident_id: UUID,
    limit: int = 25,
    offset: int = 0,
    include_unlinked: bool = False,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:incidents"])
    ),
) -> AlertWithIncidentLinkMetadataPaginatedResultsDto:
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
    db_alerts_and_links, total_count = get_incident_alerts_and_links_by_incident_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
        include_unlinked=include_unlinked,
    )

    enriched_alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts_and_links)
    logger.info(
        "Fetched alerts from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return AlertWithIncidentLinkMetadataPaginatedResultsDto(
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
    workflow_executions, total_count = get_workflow_executions_for_incident_or_alert(
        tenant_id=tenant_id,
        incident_id=str(incident_id),
        limit=limit,
        offset=offset,
    )

    workflow_execution_dtos = [
        WorkflowExecutionDTO(**we._mapping) for we in workflow_executions
    ]

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
    alert_fingerprints: List[str],
    is_created_by_ai: bool = False,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    await incident_bl.add_alerts_to_incident(
        incident_id, alert_fingerprints, is_created_by_ai
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
    fingerprints: List[str],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session=Depends(get_session),
    pusher_client: Pusher | None = Depends(get_pusher_client),
):
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    incident_bl.delete_alerts_from_incident(
        incident_id=incident_id, alert_fingerprints=fingerprints
    )
    return Response(status_code=202)


@router.post(
    "/event/{provider_type}",
    description="Receive an alert event from a provider",
    status_code=202,
)
async def receive_event(
    provider_type: str,
    bg_tasks: BackgroundTasks,
    request: Request,
    provider_id: str | None = None,
    event=Depends(extract_generic_body),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
) -> dict[str, str]:
    trace_id = request.state.trace_id
    logger.info(
        "Received event",
        extra={
            "trace_id": trace_id,
            "tenant_id": authenticated_entity.tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
        },
    )

    provider_class = None
    try:
        provider_class = ProvidersFactory.get_provider_class(provider_type)
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=400, detail=f"Provider {provider_type} not found"
        )
    if not provider_class:
        raise HTTPException(
            status_code=400, detail=f"Provider {provider_type} not found"
        )

    # Parse the raw body
    event = provider_class.format_incident(
        event, authenticated_entity.tenant_id, provider_type, provider_id
    )

    if REDIS:
        redis: ArqRedis = await get_pool()
        job = await redis.enqueue_job(
            "async_process_incident",
            authenticated_entity.tenant_id,
            provider_id,
            provider_type,
            event,
            trace_id,
            _queue_name=KEEP_ARQ_QUEUE_BASIC,
        )
        logger.info(
            "Enqueued job",
            extra={
                "job_id": job.job_id,
                "tenant_id": authenticated_entity.tenant_id,
                "queue": KEEP_ARQ_QUEUE_BASIC,
            },
        )
    else:
        logger.info("Processing incident in the background")
        bg_tasks.add_task(
            process_incident,
            {},
            authenticated_entity.tenant_id,
            provider_id,
            provider_type,
            event,
            trace_id,
        )
    return Response(status_code=202)


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

    with_alerts = (
        change.status == IncidentStatus.RESOLVED
        or change.status == IncidentStatus.ACKNOWLEDGED
    )
    incident = get_incident_by_id(tenant_id, incident_id, with_alerts=with_alerts)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # We need to do something only if status really changed
    if not change.status == incident.status:
        end_time = (
            datetime.utcnow() if change.status == IncidentStatus.RESOLVED else None
        )
        change_incident_status_by_id(tenant_id, incident_id, change.status, end_time)
        if change.status in [IncidentStatus.RESOLVED, IncidentStatus.ACKNOWLEDGED]:
            for alert in incident._alerts:
                _enrich_alert(
                    EnrichAlertRequestBody(
                        enrichments={"status": change.status.value},
                        fingerprint=alert.fingerprint,
                    ),
                    authenticated_entity=authenticated_entity,
                )
        incident.end_time = end_time
        incident.status = change.status

    new_incident_dto = IncidentDto.from_db_incident(incident)

    return new_incident_dto


@router.post(
    "/{incident_id}/severity",
    description="Change incident severity",
    response_model=IncidentDto,
)
def change_incident_severity(
    incident_id: UUID,
    change: IncidentSeverityChangeDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session: Session = Depends(get_session),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> IncidentDto:
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Changing the severity of an incident",
        extra={
            "incident_id": incident_id,
            "tenant_id": tenant_id,
            "severity": change.severity.value,
        },
    )
    incident_bl = IncidentBl(
        tenant_id, session, pusher_client, user=authenticated_entity.email
    )
    incident_dto = incident_bl.update_severity(
        incident_id, change.severity, change.comment
    )
    return incident_dto


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
        ActionType.INCIDENT_COMMENT,
        change.comment,
    )

    if pusher_client:
        pusher_client.trigger(
            f"private-{authenticated_entity.tenant_id}", "incident-comment", {}
        )

    logger.info("Added comment to incident", extra=extra)
    return comment


@router.post(
    "/ai/suggest",
    description="Create incident with AI",
    response_model=IncidentsClusteringSuggestion,
    status_code=202,
)
async def create_with_ai(
    alerts_fingerprints: List[str],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session: Session = Depends(get_session),
) -> IncidentsClusteringSuggestion:
    tenant_id = authenticated_entity.tenant_id

    # Get alerts data
    alerts = get_last_alerts(tenant_id, fingerprints=alerts_fingerprints)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)

    # Get topology data
    topology_data = TopologiesService.get_all_topology_data(tenant_id, session)

    # Create suggestions using AI
    suggestion_bl = AISuggestionBl(tenant_id, session)
    return suggestion_bl.suggest_incidents(
        alerts_dto=alerts_dto,
        topology_data=topology_data,
        user_id=authenticated_entity.email,
    )


@router.post(
    "/ai/{suggestion_id}/commit",
    description="Commit incidents with AI and user feedback",
    response_model=List[IncidentDto],
    status_code=202,
)
async def commit_with_ai(
    suggestion_id: UUID,
    incidents_with_feedback: List[IncidentCommit],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session: Session = Depends(get_session),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> List[IncidentDto]:
    tenant_id = authenticated_entity.tenant_id

    # Create business logic instances
    ai_feedback_bl = AISuggestionBl(tenant_id, session)
    incident_bl = IncidentBl(tenant_id, session, pusher_client)

    # Commit incidents with feedback
    committed_incidents = await ai_feedback_bl.commit_incidents(
        suggestion_id=suggestion_id,
        incidents_with_feedback=[
            incident.dict() for incident in incidents_with_feedback
        ],
        user_id=authenticated_entity.email,
        incident_bl=incident_bl,
    )

    # Notify about changes if pusher client is available
    if pusher_client:
        try:
            pusher_client.trigger(
                f"private-{tenant_id}",
                "incident-change",
                {},
            )
        except Exception as e:
            logger.error(f"Failed to notify client: {str(e)}")

    return committed_incidents


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
    "/{incident_id}/enrich",
    description="Enrich incident with additional data",
    status_code=202,
)
async def enrich_incident(
    incident_id: UUID,
    enrichment: EnrichIncidentRequestBody,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> IncidentDto:
    """Enrich incident with additional data."""
    tenant_id = authenticated_entity.tenant_id

    # Get incident to verify it exists
    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Use the existing enrichment infrastructure
    enrichment_bl = EnrichmentsBl(tenant_id)
    enrichment_bl.enrich_entity(
        fingerprint=str(incident_id),  # Use incident_id as fingerprint
        enrichments=enrichment.enrichments,
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee=authenticated_entity.email,
        action_description=f"Incident enriched by {authenticated_entity.email}",
        force=enrichment.force,
    )

    # Notify clients if pusher is available
    if pusher_client:
        try:
            pusher_client.trigger(
                f"private-{tenant_id}",
                "incident-change",
                {},
            )
        except Exception as e:
            logger.exception(
                "Failed to notify clients about incident change",
                extra={"error": str(e)},
            )

    return Response(status_code=202)
