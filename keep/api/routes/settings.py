import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import get_session
from keep.api.core.dependencies import verify_bearer_token
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
    keep_webhook_api_url = f"{api_url}/alerts/event/{{PROVIDER_TYPE}}"
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    return WebhookSettings(webhookApi=keep_webhook_api_url, apiKey=webhook_api_key)


@router.get("/users", description="Get all users")
def get_users(tenant_id: str = Depends(verify_bearer_token)) -> list[User]:
    auth0 = getAuth0Client()
    users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
    return [User(**user) for user in users.get("users", [])]


@router.delete("/users/{user_email}", description="Delete a user")
def delete_user(user_email: str, tenant_id: str = Depends(verify_bearer_token)):
    auth0 = getAuth0Client()
    users = auth0.users.list(q=f'app_metadata.keep_tenant_id:"{tenant_id}"')
    for user in users.get("users", []):
        if user["email"] == user_email:
            auth0.users.delete(user["user_id"])
            return {"status": "OK"}
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_email}", description="Create a user")
def create_user(user_email: str, tenant_id: str = Depends(verify_bearer_token)):
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
