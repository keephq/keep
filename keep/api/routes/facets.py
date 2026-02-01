import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

import keep.api.core.facets as facets
from keep.api.models.facet import CreateFacetDto, FacetDto
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

# Mapping of entity name to entity type
# TODO: Maybe we need to migrate current facets to match endpoint entity names
entity_name_to_entity_type = {
    "incidents": "incident",
    "alerts": "alert",
    "workflows": "workflow",
}

@router.post(
    "",
    description="Add facet for {entity_name}",
)
async def add_facet(
    entity_name: str,
    create_facet_dto: CreateFacetDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    )
) -> FacetDto:
    if entity_name not in entity_name_to_entity_type:
        raise HTTPException(status_code=409, detail="Entity not found")    
    entity_type = entity_name_to_entity_type[entity_name]
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Creating facet for incident",
        extra={
            "tenant_id": tenant_id,
        },
    )
    created_facet = facets.create_facet(
        tenant_id=tenant_id,
        entity_type=entity_type,
        facet=create_facet_dto
    )
    return created_facet

@router.delete(
    "/{facet_id}",
    description="Delete facet for {enity_name}",
)
async def delete_facet(
    facet_id: str,
    entity_name: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    )
):
    if entity_name not in entity_name_to_entity_type:
        raise HTTPException(status_code=409, detail="Entity not found")
    entity_type = entity_name_to_entity_type[entity_name]
    tenant_id = authenticated_entity.tenant_id
    logger.info(
        "Deleting facet for incident",
        extra={
            "tenant_id": tenant_id,
            "facet_id": facet_id,
        },
    )
    is_deleted = facets.delete_facet(
        tenant_id=tenant_id,
        entity_type=entity_type,
        facet_id=facet_id
    )
    
    if not is_deleted:
        raise HTTPException(status_code=404, detail="Facet not found")
