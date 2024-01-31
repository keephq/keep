import logging
import os
import secrets
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel, Field

from keep.api.core.db import (
    get_user as get_user_from_db,
    get_user_by_api_key as get_user_by_api_key_from_db,
    get_users as get_users_from_db,
    create_user as create_user_in_db,
    delete_user as delete_user_from_db
)

from keep.api.core.config import AuthenticationType
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.models.user import User
from keep.api.utils.auth0_utils import getAuth0Client
from keep.api.core.rbac import Admin as AdminRole

router = APIRouter()
logger = logging.getLogger(__name__)

class CreateUserRequest(BaseModel):
    email: str = Field(alias="username")
    password: Optional[str] = None # auth0 does not need password
    role: str

    class Config:
        allow_population_by_field_name = True

@router.get(
    "",
    description="Get all users"
)
def get_users(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:settings"])
    ),
) -> list[User]:
    tenant_id = authenticated_entity.tenant_id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.MULTI_TENANT.value
    ):
        return _get_users_auth0(tenant_id)

    return _get_users_db(tenant_id)

def _get_users_auth0(tenant_id: str) -> list[User]:
    auth0 = getAuth0Client()
    users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
    users = [
        User(
            email=user["email"],
            name=user["name"],
            # for backwards compatibility we return admin if no role is set
            role=user.get("app_metadata", {}).get("keep_role", AdminRole.get_name()),
            last_login=user.get("last_login", None),
            created_at=user["created_at"],
            picture=user["picture"],
        )
        for user in users.get("users", [])
    ]
    return users


def _get_users_db(tenant_id: str) -> list[User]:
    users = get_users_from_db()
    users = [
        User(
            email=f"{user.username}",
            name=user.username,
            role=user.role,
            last_login=str(user.last_sign_in),
            created_at=str(user.created_at),
        )
        for user in users
    ]
    return users

@router.delete(
    "/{user_email}",
    description="Delete a user")
def delete_user(
    user_email: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["delete:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.MULTI_TENANT.value
    ):
        return _delete_user_auth0(user_email, tenant_id)

    return _delete_user_db(user_email, tenant_id)


def _delete_user_auth0(user_email: str, tenant_id: str) -> dict:
    auth0 = getAuth0Client()
    users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
    for user in users.get("users", []):
        if user["email"] == user_email:
            auth0.users.delete(user["user_id"])
            return {"status": "OK"}
    raise HTTPException(status_code=404, detail="User not found")


def _delete_user_db(user_email: str, tenant_id: str) -> dict:
    try:
        delete_user_from_db(user_email)
        return {"status": "OK"}
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    
@router.post("",
             description="Create a user")
async def create_user(
    request_data: CreateUserRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    user_email = request_data.email
    password = request_data.password
    role = request_data.role

    if not user_email:
        raise HTTPException(status_code=400, detail="Email is required")

    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.MULTI_TENANT.value
    ):
        return _create_user_auth0(user_email, tenant_id, role)

    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    return _create_user_db(tenant_id, user_email, password, role)


def _create_user_auth0(user_email: str, tenant_id: str, role: str) -> dict:
    auth0 = getAuth0Client()
    # User email can exist in 1 tenant only for now.
    users = auth0.users.list(q=f'email:"{user_email}"')
    if users.get("users", []):
        raise HTTPException(status_code=409, detail="User already exists")
    user = auth0.users.create(
        {
            "email": user_email,
            "password": secrets.token_urlsafe(13),
            "email_verified": True,
            "app_metadata": {"keep_tenant_id": tenant_id, "keep_role": role},
            "connection": "keep-users",  # TODO: move to env
        }
    )
    user_dto = User(
        email=user["email"],
        name=user["name"],
        # for backwards compatibility we return admin if no role is set
        role=user.get("app_metadata", {}).get("keep_role", AdminRole.get_name()),
        last_login=user.get("last_login", None),
        created_at=user["created_at"],
        picture=user["picture"],
    )
    return user_dto


def _create_user_db(tenant_id: str, user_email: str, password: str, role: str) -> dict:
    try:
        user = create_user_in_db(tenant_id, user_email, password, role)
        return User(
            email=user_email,
            name=user_email,
            role=role,
            last_login=None,
            created_at=str(user.created_at),
        )
    except Exception:
        raise HTTPException(status_code=409, detail="User already exists")


