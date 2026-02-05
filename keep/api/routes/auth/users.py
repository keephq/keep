import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from keep.api.models.user import User
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateUserRequest(BaseModel):
    email: str = Field(alias="username")
    name: Optional[str] = None
    password: Optional[str] = None  # auth0 does not need password
    role: Optional[str] = (
        None  # user can be assigned to group and get its roles from groups
    )
    groups: Optional[list[str]] = None

    class Config:
        allow_population_by_field_name = True


class UpdateUserRequest(BaseModel):
    email: Optional[str] = Field(alias="username")
    password: Optional[str] = None
    role: Optional[str] = Field(default=None)
    groups: Optional[list[str]] = None

    class Config:
        allow_population_by_field_name = True

    @validator("role", allow_reuse=True)
    def validate_role(cls, v):
        if v == "":
            return None
        return v


@router.get("", description="Get all users")
def get_users(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> list[User]:
    identity_manager = IdentityManagerFactory.get_identity_manager(
        authenticated_entity.tenant_id
    )
    return identity_manager.get_users()


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
    user_name = request_data.name
    password = request_data.password
    role = request_data.role
    groups = request_data.groups

    if not user_email:
        raise HTTPException(status_code=400, detail="Email is required")

    identity_manager = IdentityManagerFactory.get_identity_manager(tenant_id)
    return identity_manager.create_user(
        user_email=user_email,
        user_name=user_name,
        password=password,
        role=role,
        groups=groups,
    )


@router.put("/{user_email}", description="Update a user")
async def update_user(
    user_email: str,
    request_data: UpdateUserRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    identity_manager = IdentityManagerFactory.get_identity_manager(tenant_id)

    update_data = request_data.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    try:
        return identity_manager.update_user(user_email, update_data)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Updating users is not supported by this identity manager",
        )
