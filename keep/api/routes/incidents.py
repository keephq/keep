import asyncio
import logging
import os
import pathlib
import sys
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pusher import Pusher
from pydantic.types import UUID
from sqlmodel import Session

from keep.api.bl.ai_suggestion_bl import AISuggestionBl
from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.db import (
    add_audit,
    change_incident_status_by_id,
    confirm_predicted_incident_by_id,
    delete_incident_by_id,
    get_future_incidents_by_incident_id,
    get_incident_alerts_and_links_by_incident_id,
    get_incident_by_id,
    get_incidents_meta_for_tenant,
    get_last_alerts,
    get_last_incidents,
    get_session,
    get_workflow_executions_for_incident_or_alert,
    remove_alerts_to_incident_by_incident_id,
    update_incident_from_dto_by_id,
)
from keep.api.core.dependencies import get_pusher_client
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
from keep.api.models.db.ai_suggestion import AISuggestionType
from keep.api.models.db.alert import AlertActionType, AlertAudit
from keep.api.routes.alerts import _enrich_alert
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.import_ee import mine_incidents_and_create_objects
from keep.api.utils.pagination import (
    AlertWithIncidentLinkMetadataPaginatedResultsDto,
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
    workflow_execution_dtos, total_count = (
        get_workflow_executions_for_incident_or_alert(
            tenant_id=tenant_id,
            incident_id=str(incident_id),
            limit=limit,
            offset=offset,
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
    is_created_by_ai: bool = False,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    pusher_client: Pusher | None = Depends(get_pusher_client),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    incident_bl.add_alerts_to_incident(incident_id, alert_ids)
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


import json  # noqa
from typing import List  # noqa

from pydantic import BaseModel, Field  # noqa

from keep.topologies.topologies_service import TopologiesService  # noqa


class Alert(BaseModel):
    id: str
    description: str


class Incident(BaseModel):
    incident_name: str
    alerts: List[int] = Field(
        description="List of alert numbers (1-based index) included in this incident"
    )
    reasoning: str
    severity: str = Field(
        description="Assessed severity level",
        enum=["Low", "Medium", "High", "Critical"],
    )
    recommended_actions: List[str]
    confidence_score: float = Field(
        description="Confidence score of the incident clustering (0.0 to 1.0)"
    )
    confidence_explanation: str = Field(
        description="Explanation of how the confidence score was calculated"
    )


class IncidentClustering(BaseModel):
    incidents: List[Incident]


class IncidentCommit(BaseModel):
    accepted: bool
    original_suggestion: dict
    changes: dict = Field(default_factory=dict)
    incident: IncidentDto


class IncidentSuggestion(BaseModel):
    incident_suggestion: list[IncidentDto]
    suggestion_id: str


@router.post(
    "/ai/suggest",
    description="Create incident with AI",
    response_model=IncidentSuggestion,
    status_code=202,
)
async def create_with_ai(
    alerts_fingerprints: List[str],
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session: Session = Depends(get_session),
    pusher_client: Pusher | None = Depends(get_pusher_client),
) -> IncidentSuggestion:

    tenant_id = authenticated_entity.tenant_id
    suggestion_bl = AISuggestionBl(tenant_id, session)

    # check if the user has already provided a similar suggestion
    suggestion_input = {"alerts_fingerprints": alerts_fingerprints}
    existing_suggestion = suggestion_bl.get_suggestion_by_input(suggestion_input)
    if existing_suggestion:
        logger.info("Retrieving existing suggestion from DB")
        alerts = get_last_alerts(tenant_id, fingerprints=alerts_fingerprints)
        alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
        incident_clustering = IncidentClustering.parse_obj(
            existing_suggestion.suggestion_content
        )
        processed_incidents = process_incidents(
            incident_clustering.incidents, alerts_dto
        )
        return IncidentSuggestion(
            incident_suggestion=processed_incidents,
            suggestion_id=str(existing_suggestion.id),
        )

    if len(alerts_fingerprints) > 50:
        raise HTTPException(status_code=400, detail="Too many alerts to process")

    logger.info(
        "Creating incident with AI",
        extra={
            "alerts_fingerprints": alerts_fingerprints,
            "tenant_id": tenant_id,
        },
    )
    alerts = get_last_alerts(tenant_id, fingerprints=alerts_fingerprints)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    topology_data = TopologiesService.get_all_topology_data(tenant_id, session)
    alert_descriptions = "\n".join(
        [
            f"Alert {idx+1}: {json.dumps(alert.dict())}"
            for idx, alert in enumerate(alerts_dto)
        ]
    )

    topology_data = "\n".join(
        [
            f"Topology {idx+1}: {json.dumps(topology.dict(), default=str)}"
            for idx, topology in enumerate(topology_data)
        ]
    )

    system_prompt = """
    You are an advanced AI system specializing in IT operations and incident management.
    Your task is to analyze the provided IT operations alerts and topology data, and cluster them into meaningful incidents.
    Consider factors such as:
    1. Alert description and content
    2. Potential temporal proximity
    3. Affected systems or services
    4. Type of IT issue (e.g., performance degradation, service outage, resource utilization)
    5. Potential root causes
    6. Relationships and dependencies between services in the topology data

    Group related alerts into distinct incidents and provide a detailed analysis for each incident.
    For each incident:
    1. Assess its severity
    2. Recommend initial actions for the IT operations team
    3. Provide a confidence score (0.0 to 1.0) for the incident clustering
    4. Explain how the confidence score was calculated, considering factors like alert similarity, topology relationships, and the strength of the correlation between alerts

    Use the topology data to improve your incident clustering by considering service dependencies and relationships.
    """

    user_prompt = f"""
    Analyze the following IT operations alerts and topology data, then group the alerts into incidents:

    Alerts:
    {alert_descriptions}

    Topology data:
    {topology_data}

    Provide your analysis and clustering in the specified JSON format.
    """

    try:
        from openai import OpenAI

        client = OpenAI()
        completion = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_clustering",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "incidents": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "incident_name": {"type": "string"},
                                        "alerts": {
                                            "type": "array",
                                            "items": {"type": "integer"},
                                            "description": "List of alert numbers (1-based index) included in this incident",
                                        },
                                        "reasoning": {"type": "string"},
                                        "severity": {
                                            "type": "string",
                                            "enum": [
                                                "critical",
                                                "high",
                                                "warning",
                                                "info",
                                                "low",
                                            ],
                                            "description": "Assessed severity level",
                                        },
                                        "recommended_actions": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "confidence_score": {
                                            "type": "number",
                                            "description": "Confidence score of the incident clustering (0.0 to 1.0)",
                                        },
                                        "confidence_explanation": {
                                            "type": "string",
                                            "description": "Explanation of how the confidence score was calculated",
                                        },
                                    },
                                    "required": [
                                        "incident_name",
                                        "alerts",
                                        "reasoning",
                                        "severity",
                                        "recommended_actions",
                                        "confidence_score",
                                        "confidence_explanation",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["incidents"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            temperature=0.2,
        )

        incident_clustering = IncidentClustering.parse_raw(
            completion.choices[0].message.content
        )

        # add the suggestion to the database
        suggestion = suggestion_bl.add_suggestion(
            user_id=authenticated_entity.email,
            suggestion_input=suggestion_input,
            suggestion_type=AISuggestionType.INCIDENT_SUGGESTION,
            suggestion_content=incident_clustering.dict(),
            model="gpt-4o-2024-08-06",
        )

        # Process the incidents
        processed_incidents = process_incidents(
            incident_clustering.incidents, alerts_dto
        )

        return IncidentSuggestion(
            incident_suggestion=processed_incidents,
            suggestion_id=str(suggestion.id),
        )

    except Exception as e:
        logger.error(f"AI incident creation failed: {e}")
        raise HTTPException(status_code=500, detail="AI service is unavailable.")


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
    ai_feedback_bl = AISuggestionBl(tenant_id, session)
    incident_bl = IncidentBl(tenant_id, session, pusher_client)
    committed_incidents = []

    # Add feedback to the database
    changes = {
        incident_commit.incident.id: incident_commit.changes
        for incident_commit in incidents_with_feedback
    }
    ai_feedback_bl.add_feedback(
        suggestion_id=suggestion_id,
        user_id=authenticated_entity.email,
        feedback_content=changes,
    )

    for incident_with_feedback in incidents_with_feedback:
        if not incident_with_feedback.accepted:
            logger.info(
                f"Incident {incident_with_feedback.incident.name} rejected by user, skipping creation"
            )
            continue

        try:

            # Create the incident
            created_incident = incident_bl.create_incident(
                incident_with_feedback.incident
            )

            # Add alerts to the created incident
            alert_ids = [
                uuid.UUID(alert.get("event_id"))
                for alert in incident_with_feedback.incident.alerts
            ]
            incident_bl.add_alerts_to_incident(created_incident.id, alert_ids)

            committed_incidents.append(created_incident)
            logger.info(
                f"Incident {incident_with_feedback.incident.name} created successfully"
            )

        except Exception as e:
            logger.error(
                f"Failed to create incident {incident_with_feedback.incident.name}: {str(e)}"
            )

    return committed_incidents


def process_incidents(
    incidents: List[Incident], alerts_dto: List[AlertDto]
) -> List[IncidentDto]:
    processed_incidents = []
    for incident in incidents:
        alert_sources = set()
        alert_services = set()
        for alert_index in incident.alerts:
            # TODO: more than one source?
            alert = alerts_dto[alert_index - 1]
            alert_sources.add(alert.source[0])
            if alert.service:
                alert_services.add(alert.service)

        # start time is the earliest alert time
        incident_alerts = [alerts_dto[i - 1] for i in incident.alerts]
        start_time = min([alert.lastReceived for alert in incident_alerts])
        last_seen_time = max([alert.lastReceived for alert in incident_alerts])

        incident_dto = IncidentDto(
            id=uuid.uuid4(),
            name=incident.incident_name,
            start_time=start_time,
            last_seen_time=last_seen_time,
            description=incident.reasoning,
            confidence_score=incident.confidence_score,
            confidence_explanation=incident.confidence_explanation,
            severity=incident.severity,
            alert_ids=[alerts_dto[i - 1].id for i in incident.alerts],
            recommended_actions=incident.recommended_actions,
            is_predicted=True,
            is_confirmed=False,
            alerts_count=len(incident.alerts),
            alert_sources=list(alert_sources),
            alerts=incident_alerts,  # return the alerts as well
            services=list(alert_services),
        )
        processed_incidents.append(incident_dto)
    return processed_incidents
