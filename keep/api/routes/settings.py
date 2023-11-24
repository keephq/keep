import io
import json
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from typing import Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from keep.api.core.config import AuthenticationType, config
from keep.api.core.db import create_user as create_user_in_db
from keep.api.core.db import delete_user as delete_user_from_db
from keep.api.core.db import get_session
from keep.api.core.db import get_users as get_users_from_db
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.alert import AlertDto
from keep.api.models.smtp import SMTPSettings
from keep.api.models.user import User
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.auth0_utils import getAuth0Client
from keep.api.utils.tenant_utils import get_or_create_api_key
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

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
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.MULTI_TENANT.value
    ):
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
            last_login=str(user.last_sign_in),
            created_at=str(user.created_at),
        )
        for user in users
    ]
    return users


@router.delete("/users/{user_email}", description="Delete a user")
def delete_user(user_email: str, tenant_id: str = Depends(verify_bearer_token)):
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value).lower()
        == AuthenticationType.MULTI_TENANT.value
    ):
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
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_email}", description="Create a user")
async def create_user(
    user_email: str,
    request: Request = None,
    tenant_id: str = Depends(verify_bearer_token),
):
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value).lower()
        == AuthenticationType.MULTI_TENANT.value
    ):
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
    except Exception:
        raise HTTPException(status_code=409, detail="User already exists")


@router.post("/smtp", description="Install or update SMTP settings")
async def update_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    tenant_id: str = Depends(verify_bearer_token),
):
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
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
):
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    try:
        smtp_settings = secret_manager.read_secret(secret_name="smtp")
        smtp_settings = json.loads(smtp_settings)
        return JSONResponse(status_code=200, content=smtp_settings)
    except Exception:
        # everything ok but no smtp settings
        return JSONResponse(status_code=200, content={})


@router.delete("/smtp", description="Delete SMTP settings")
async def delete_smtp_settings(
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
):
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    secret_manager.delete_secret(secret_name="smtp")
    return JSONResponse(status_code=200, content={})


@router.post("/smtp/test", description="Test SMTP settings")
async def test_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    tenant_id: str = Depends(verify_bearer_token),
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


@router.get("/apikey")
def get_api_key(
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
):
    # get the api key for the CLI
    api_key = get_or_create_api_key(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id="cli",
        system_description="API key",
    )
    return {"apiKey": api_key}
