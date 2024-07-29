import logging
from typing import List

from fastapi import APIRouter, Body, Depends

from keep.api.models.user import ResourcePermission
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", description="Get resources permissions")
def get_permissions(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> List[ResourcePermission]:
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    permissions = identity_manager.get_permissions()
    return permissions


@router.post("", description="Create permissions for resources")
def create_permissions(
    resource_permissions: List[ResourcePermission] = Body(
        ..., description="List of resource permissions"
    ),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    identity_manager.create_permissions(resource_permissions)
    return {"message": "Permissions created successfully"}
