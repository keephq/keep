import io
import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import get_session
from keep.api.models.alert import AlertDto
from keep.api.models.smtp import SMTPSettings
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.tenant_utils import (
    create_api_key,
    get_api_key,
    get_api_keys,
    get_api_keys_secret,
    get_or_create_api_key,
    update_api_key_internal,
    APIKeyException,
)
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.identitymanager.rbac import get_role_by_role_name
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
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
) -> WebhookSettings:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting webhook settings")
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event"
    try:
        webhook_api_key = get_or_create_api_key(
            session=session,
            tenant_id=tenant_id,
            created_by="system",
            unique_api_key_id="webhook",
            system_description="Webhooks API key",
        )
    except Exception as e:
        logger.error(f"Error retrieving webhook settings: {str(e)}")
        return JSONResponse(
            status_code=502,
            content={"message": str(e)},
        )
    logger.info("Webhook settings retrieved successfully")
    return WebhookSettings(
        webhookApi=keep_webhook_api_url,
        apiKey=webhook_api_key,
        modelSchema=AlertDto.schema(),
    )


@router.post("/smtp", description="Install or update SMTP settings")
async def update_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Save the SMTP settings in the secret manager
    smtp_settings = smtp_settings.dict()
    smtp_settings["password"] = smtp_settings["password"].get_secret_value()
    secret_manager.write_secret(
        secret_name=f"{tenant_id}_smtp", secret_value=json.dumps(smtp_settings)
    )
    return {"status": "SMTP settings updated successfully"}


@router.get("/smtp", description="Get SMTP settings")
async def get_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Getting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    try:
        smtp_settings = secret_manager.read_secret(secret_name=f"{tenant_id}_smtp")
        smtp_settings = json.loads(smtp_settings)
        logger.info("SMTP settings retrieved successfully")
        return JSONResponse(status_code=200, content=smtp_settings)
    except Exception:
        # everything ok but no smtp settings
        return JSONResponse(status_code=200, content={})


@router.delete("/smtp", description="Delete SMTP settings")
async def delete_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Deleting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    secret_manager.delete_secret(secret_name=f"{tenant_id}_smtp")
    logger.info("SMTP settings deleted successfully")
    return JSONResponse(status_code=200, content={})


@router.post("/smtp/test", description="Test SMTP settings")
async def test_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
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
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    try:
        identity_manager = IdentityManagerFactory.get_identity_manager(
            tenant_id=authenticated_entity.tenant_id,
        )
        body = await request.json()
        unique_api_key_id = body["name"].replace(" ", "")
        role = identity_manager.get_role_by_role_name(body["role"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    try:
        api_key = create_api_key(
            session=session,
            tenant_id=authenticated_entity.tenant_id,
            created_by=authenticated_entity.email,
            unique_api_key_id=unique_api_key_id,
            role=role.name,
            is_system=False,
        )

        tenant_api_key = get_api_key(
            session,
            unique_api_key_id=unique_api_key_id,
            tenant_id=authenticated_entity.tenant_id,
        )

        return {
            "reference_id": tenant_api_key.reference_id,
            "tenant": tenant_api_key.tenant,
            "is_deleted": tenant_api_key.is_deleted,
            "created_at": tenant_api_key.created_at,
            "created_by": tenant_api_key.created_by,
            "last_used": tenant_api_key.last_used,
            "secret": api_key,
            "role": tenant_api_key.role,
        }
    except APIKeyException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error creating API key: {str(e)}",
        )


@router.get("/apikeys", description="Get API keys")
def get_keys(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    role = get_role_by_role_name(authenticated_entity.role)

    logger.info(f"Getting active API keys for tenant {tenant_id}")

    api_keys = get_api_keys(
        session=session,
        tenant_id=tenant_id,
        email=authenticated_entity.email,
        role=role,
    )

    if api_keys:
        api_keys = get_api_keys_secret(tenant_id=tenant_id, api_keys=api_keys)

    logger.info(
        f"Active API keys for tenant {tenant_id} retrieved successfully",
    )

    return {"apiKeys": api_keys}


@router.put("/apikey", description="Update API key secret")
async def update_api_key(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    try:
        body = await request.json()
        unique_api_key_id = body["apiKeyId"]
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
        return {"message": "API key secret updated", "apiKey": api_key}
    else:
        logger.info(f"Api key ({unique_api_key_id}) not found")
        raise HTTPException(
            status_code=404, detail=f"API key ({unique_api_key_id}) not found"
        )


@router.delete("/apikey/{keyId}", description="Delete API key")
def delete_api_key(
    keyId: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info(f"Deleting api key ({keyId})")
    tenant_id = authenticated_entity.tenant_id
    api_key = get_api_key(
        session, unique_api_key_id=keyId, tenant_id=authenticated_entity.tenant_id
    )

    if api_key and api_key.is_deleted is False:
        try:
            context_manager = ContextManager(tenant_id=tenant_id)
            secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
            secret_manager.delete_secret(
                secret_name=f"{tenant_id}-{api_key.reference_id}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to deactivate Api key ({keyId}) secret. Error: {str(e)}",
            )

        try:
            api_key.is_deleted = True
            session.commit()
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to flag Api key ({keyId}) as deactivated",
            )

        logger.info(f"Api key ({keyId}) has been deactivated")
        return {"message": "Api key has been deactivated"}
    else:
        logger.info(f"Api key ({keyId}) not found")
        raise HTTPException(status_code=404, detail=f"Api key ({keyId}) not found")


@router.get("/sso")
async def get_sso_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    identity_manager = IdentityManagerFactory.get_identity_manager(
        tenant_id=authenticated_entity.tenant_id,
        context_manager=ContextManager(tenant_id=authenticated_entity.tenant_id),
    )

    if identity_manager.support_sso:
        providers = identity_manager.get_sso_providers()
        return {
            "sso": True,
            "providers": providers,
            "wizardUrl": identity_manager.get_sso_wizard_url(authenticated_entity),
        }
    else:
        return {"sso": False}
