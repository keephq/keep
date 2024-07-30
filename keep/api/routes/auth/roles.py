import logging

from fastapi import APIRouter, Body, Depends

from keep.api.models.user import Role
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", description="Get roles")
def get_roles(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> list[Role]:
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    roles = identity_manager.get_roles()
    return roles


@router.post("", description="Create role")
def create_role(
    role: Role = Body(..., description="Role"),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    role = identity_manager.create_role(role)
    return role
