import io
import json
import logging
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from typing import Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from keep.api.core.config import AuthenticationType, config
from keep.api.core.db import create_user as create_user_in_db
from keep.api.core.db import delete_user as delete_user_from_db
from keep.api.core.db import get_session
from keep.api.core.db import get_users as get_users_from_db
from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.alert import AlertDto
from keep.api.models.smtp import SMTPSettings
from keep.api.models.user import User
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.auth0_utils import getAuth0Client
from keep.api.utils.tenant_utils import get_api_keys_secret, get_or_create_api_key, update_api_key_internal, delete_api_key_internal, create_api_key, get_api_keys
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


class CreateUserRequest(BaseModel):
    email: str = Field(alias="username")
    password: Optional[str] = None  # for auth0 we don't need a password
    role: str

    class Config:
        allow_population_by_field_name = True


@router.get(
    "/webhook",
    description="Get details about the webhook endpoint (e.g. the API url and an API key)",
)
def webhook_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
) -> WebhookSettings:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting webhook settings")
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event"
    webhook_api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        created_by="system",
        unique_api_key_id="webhook",
        system_description="Webhooks API key",
    )
    logger.info("Webhook settings retrieved successfully")
    return WebhookSettings(
        webhookApi=keep_webhook_api_url,
        apiKey=webhook_api_key,
        modelSchema=AlertDto.schema(),
    )


@router.get("/users", description="Get all users")
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


@router.delete("/users/{user_email}", description="Delete a user")
def delete_user(
    user_email: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["delete:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value).lower()
        == AuthenticationType.MULTI_TENANT.value.lower()
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


@router.post("/users", description="Create a user")
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
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value).lower()
        == AuthenticationType.MULTI_TENANT.value.lower()
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


@router.post("/smtp", description="Install or update SMTP settings")
async def update_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Save the SMTP settings in the secret manager
    smtp_settings = smtp_settings.dict()
    smtp_settings["password"] = smtp_settings["password"].get_secret_value()
    secret_manager.write_secret(
        secret_name="smtp", secret_value=json.dumps(smtp_settings)
    )
    return {"status": "SMTP settings updated successfully"}


@router.get("/smtp", description="Get SMTP settings")
async def get_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Getting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    try:
        smtp_settings = secret_manager.read_secret(secret_name="smtp")
        smtp_settings = json.loads(smtp_settings)
        logger.info("SMTP settings retrieved successfully")
        return JSONResponse(status_code=200, content=smtp_settings)
    except Exception:
        # everything ok but no smtp settings
        return JSONResponse(status_code=200, content={})


@router.delete("/smtp", description="Delete SMTP settings")
async def delete_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["delete:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Deleting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    secret_manager.delete_secret(secret_name="smtp")
    logger.info("SMTP settings deleted successfully")
    return JSONResponse(status_code=200, content={})


@router.post("/smtp/test", description="Test SMTP settings")
async def test_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
):
    # Logic to test SMTP settings, perhaps by sending a test email
    # You would use the provided SMTP settings to try and send an email
    success, message, logs = test_smtp_connection(smtp_settings)
    if success:
        return JSONResponse(status_code=200, content={"message": message, "logs": logs})
    else:
        return JSONResponse(status_code=400, content={"message": message, "logs": logs})


def test_smtp_connection(settings: SMTPSettings) -> Tuple[bool, str, str]:
    # Capture the SMTP session output
    log_stream = io.StringIO()
    try:
        # A patched version of smtplib.SMTP that captures the SMTP session output
        server = PatchedSMTP(
            settings.host, settings.port, timeout=10, log_stream=log_stream
        )
        if settings.secure:
            server.starttls()

        if settings.username and settings.password:
            server.login(settings.username, settings.password.get_secret_value())

        # Send a test email to the user's email to ensure it works
        message = MIMEText("This is a test message from the SMTP settings test.")
        message["From"] = settings.from_email
        message["To"] = settings.to_email
        message["Subject"] = "Test SMTP Settings"

        server.sendmail(settings.from_email, [settings.to_email], message.as_string())
        server.quit()
        # Get the SMTP session log
        smtp_log = log_stream.getvalue().splitlines()
        log_stream.close()

        return True, "SMTP settings are correct and an email has been sent.", smtp_log
    except Exception as e:
        return False, str(e), log_stream.getvalue().splitlines()


class PatchedSMTP(smtplib.SMTP):
    debuglevel = 1

    def __init__(
        self,
        host="",
        port=0,
        local_hostname=None,
        timeout=...,
        source_address=None,
        log_stream=None,
    ):
        self.log_stream = log_stream
        super().__init__(host, port, local_hostname, timeout, source_address)

    def _print_debug(self, *args):
        if self.log_stream is not None:
            # Write debug info to the StringIO stream
            self.log_stream.write(" ".join(str(arg) for arg in args) + "\n")
        else:
            super()._print_debug(*args)


@router.post("/apikey", description="Create API key")
async def create_key(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    try:
        body = await request.json()
        unique_api_key_id = body['name']
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    api_key = create_api_key(
        session=session,
        tenant_id=authenticated_entity.tenant_id,
        created_by=authenticated_entity.email,
        unique_api_key_id=unique_api_key_id,
        role=AdminRole,
        is_system=False,
    )

    return api_key


@router.get("/apikeys", description="Get API keys")
def get_keys(
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id

    logger.info(f"Getting active API keys for tenant {tenant_id}")

    api_keys = get_api_keys(
        session=session,
        tenant_id=tenant_id,
    )

    if api_keys:
        api_keys = get_api_keys_secret(
            tenant_id=tenant_id,
            api_keys=api_keys
        )

    logger.info(
        f"Active API keys for tenant {tenant_id} retrieved successfully",
    )

    return {"apiKeys": api_keys}


@router.put("/apikey", description="Update API key secret")
async def update_api_key(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):

    try:
        body = await request.json()
        unique_api_key_id = body['apiKeyId']
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    tenant_id = authenticated_entity.tenant_id

    logger.info(
        f"Updating API key ({unique_api_key_id}) secret",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )

    api_key = update_api_key_internal(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id=unique_api_key_id,
    )

    if api_key:
        logger.info(f"Api key ({unique_api_key_id}) secret updated")
        return {"message": "API key secret updated", "old-secret": api_key.old_api_key_secret, "new-secret": api_key.new_api_key}
    else:
        logger.info(f"Api key ({unique_api_key_id}) not found")
        raise HTTPException(status_code=404, detail=f"API key ({unique_api_key_id}) not found")


@router.delete("/apikey/{keyId}", description="Delete API key")
def delete_api_key(
    keyId: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info(f"Deleting api key ({keyId})")

    if delete_api_key_internal(
        session=session,
        tenant_id=authenticated_entity.tenant_id,
        unique_api_key_id=keyId,

    ):
        logger.info(f"Api key ({keyId}) deleted")
        return {"message": "Api key deleted"}
    else:
        logger.info(f"Api key ({keyId}) not found")
        raise HTTPException(status_code=404, detail=f"Api key ({keyId}) not found")
