import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import create_user as create_user_in_db
from keep.api.core.db import delete_user as delete_user_from_db
from keep.api.core.db import get_session
from keep.api.core.db import get_users as get_users_from_db
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.alert import AlertDto
from keep.api.models.user import User
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.auth0_utils import getAuth0Client
from keep.api.utils.tenant_utils import get_or_create_api_key

router = APIRouter()


@router.get(
    "/webhook",
    description="Get details about the webhook endpoint (e.g. the API url and an API key)",
)
def webhook_settings(
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> WebhookSettings:
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event"
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    return WebhookSettings(
        webhookApi=keep_webhook_api_url,
        apiKey=webhook_api_key,
        modelSchema=AlertDto.schema(),
    )


@router.get("/users", description="Get all users")
def get_users(tenant_id: str = Depends(verify_bearer_token)) -> list[User]:
    if os.environ.get("KEEP_MULTI_TENANT", "true") == "true":
        return _get_users_auth0(tenant_id)

    return _get_users_db(tenant_id)


def _get_users_auth0(tenant_id: str) -> list[User]:
    auth0 = getAuth0Client()
    users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
    return [User(**user) for user in users.get("users", [])]


def _get_users_db(tenant_id: str) -> list[User]:
    users = get_users_from_db()
    users = [
        User(
            email=f"{user.username}",
            name=user.username,
            last_sign_in=user.last_sign_in,
            created_at=str(user.created_at),
        )
        for user in users
    ]
    return users


@router.delete("/users/{user_email}", description="Delete a user")
def delete_user(user_email: str, tenant_id: str = Depends(verify_bearer_token)):
    if os.environ.get("KEEP_MULTI_TENANT", "true") == "true":
        return _delete_user_auth0(tenant_id)

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
    except:
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_email}", description="Create a user")
async def create_user(
    user_email: str,
    request: Request = None,
    tenant_id: str = Depends(verify_bearer_token),
):
    if os.environ.get("KEEP_MULTI_TENANT", "true") == "true":
        return _create_user_auth0(user_email, tenant_id)

    data = await request.json()
    password = data.get("password")

    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    return _create_user_db(user_email, password, tenant_id)


def _create_user_auth0(user_email: str, tenant_id: str) -> dict:
    auth0 = getAuth0Client()
    # User email can exist in 1 tenant only for now.
    users = auth0.users.list(q=f'email:"{user_email}"')
    if users.get("users", []):
        raise HTTPException(status_code=409, detail="User already exists")
    auth0.users.create(
        {
            "email": user_email,
            "password": secrets.token_urlsafe(13),
            "email_verified": True,
            "app_metadata": {"keep_tenant_id": tenant_id},
            "connection": "keep-users",  # TODO: move to env
        }
    )
    return {"status": "OK"}


def _create_user_db(user_email: str, password: str, tenant_id: str) -> dict:
    try:
        create_user_in_db(user_email, password)
        return {"status": "OK"}
    except:
        raise HTTPException(status_code=409, detail="User already exists")
