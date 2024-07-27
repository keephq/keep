import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from keep.api.models.user import User
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateUserRequest(BaseModel):
    email: str = Field(alias="username")
    password: Optional[str] = None  # auth0 does not need password
    role: str

    class Config:
        allow_population_by_field_name = True


@router.get("", description="Get all users")
def get_users(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> list[User]:
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    users = identity_manager.get_users()
    return users


@router.delete("/{user_email}", description="Delete a user")
def delete_user(
    user_email: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:settings"])
    ),
):
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    return identity_manager.delete_user(user_email)


@router.post("", description="Create a user")
async def create_user(
    request_data: CreateUserRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    user_email = request_data.email
    password = request_data.password
    role = request_data.role

    if not user_email:
        raise HTTPException(status_code=400, detail="Email is required")

    identity_manager = IdentityManagerFactory.get_identity_manager(tenant_id)
    return identity_manager.create_user(user_email, password, role)
