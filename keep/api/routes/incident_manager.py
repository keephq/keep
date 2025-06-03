import logging
from typing import List, Optional
from uuid import UUID

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic.types import UUID
from pydantic import BaseModel

from keep.api.core.config import config
from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.cel_to_sql.sql_providers.base import CelToSqlException
from keep.api.models.db.incident import IncidentSeverity, IncidentStatus
from keep.api.models.incident import (
    IncidentSorting,
)
from keep.api.utils.pagination import (
    IncidentsPaginatedResultsDto,
)
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


INCIDENT_MANAGER_URL = str(config("INCIDENT_MANAGER_URL", cast=str))


class RelatedIncidentDto(BaseModel):
    id: UUID
    user_generated_name: str
    user_summary: str


class RelatedIncidentsDto(BaseModel):
    limit: int
    offset: int
    count: int
    items: list[RelatedIncidentDto]  # Assuming items are incident IDs


async def retrieve_related_incidents(
    incident_id: str,
) -> RelatedIncidentsDto:
    """
    Retrieve related incidents based on the provided incident ID.
    
    Args:
        incident_id (str): The ID of the incident to find related incidents for.
        top_k (int): The number of related incidents to return.
    
    Returns:
        list[str]: A list of related incident IDs.
    """
    print(f"{INCIDENT_MANAGER_URL=}")
    # Placeholder for actual retrieval logic
    logger.info(f"Retrieving related incidents for incident ID: {incident_id}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{INCIDENT_MANAGER_URL}/retrieve-related-incidents",
            params={"incident_id": incident_id}
        )
        if response.status_code != 200:
            logger.error(f"Failed to retrieve related incidents: {response.text}")
            return RelatedIncidentsDto(
                limit=0,
                offset=0,
                count=0,
                items=[]
            )
        print(f"Response: {response.json()}")
        data = response.json()
        return RelatedIncidentsDto(
            limit=0,
            offset=0,
            count=len(data),
            items=[
                RelatedIncidentDto(
                    id=UUID(item["id"]),
                    user_generated_name=item["user_generated_name"],
                    user_summary=item["user_summary"]
                ) for item in data
            ]
        )


@router.get(
    "/retrieve-related-incidents/{incident_id}",
    description="Get all related incidents for a given incident ID.",
)
async def get_all_related_incidents(
    incident_id: str,
    candidate: bool = False,
    predicted: Optional[bool] = None,
    limit: int = 100,
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
    print(f"Allowed incident IDs: {allowed_incident_ids}")
    related_incidents = await retrieve_related_incidents(
        incident_id=incident_id,
    )
    related_incident_ids = [
        str(incident.id) for incident in related_incidents.items
    ]
    # use the related incident ids if not in allowed_incident_ids
    if allowed_incident_ids:
        allowed_incident_ids = [
            incident_id for incident_id in allowed_incident_ids
            if incident_id in set(related_incident_ids)
        ]
    else:
        allowed_incident_ids = related_incident_ids

    incident_bl = IncidentBl(tenant_id, session=None, pusher_client=None)

    try:
        result = incident_bl.query_incidents(
            tenant_id=tenant_id,
            is_candidate=candidate,
            is_predicted=predicted,
            limit=limit,
            offset=offset,
            sorting=sorting,
            cel=cel,
            allowed_incident_ids=allowed_incident_ids,
        )
        # reorder the result in the same order as the related incidents
        result.items.sort(
            key=lambda x: related_incident_ids.index(str(x.id))
            if str(x.id) in related_incident_ids else float('inf')
        )
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
        return result
    except CelToSqlException as e:
        logger.exception(f'Error parsing CEL expression "{cel}". {str(e)}')
        raise HTTPException(
            status_code=400, detail=f"Error parsing CEL expression: {cel}"
        ) from e

