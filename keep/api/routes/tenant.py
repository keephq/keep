import hashlib
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

# This import is required to create the tables
from keep.api.core.dependencies import get_session, verify_bearer_token
from keep.api.models.db.tenant import TenantApiKey, TenantInstallation
from keep.secretmanager.secretmanagerfactory import (
    SecretManagerFactory,
    SecretManagerTypes,
)

router = APIRouter()


@router.get(
    "/onboarded",
    description="Check if a tenant is onboarded (meaning - installed github bot)",
)
def is_onboarded(
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> JSONResponse:
    logging.getLogger().info(f"Serving request for onboarded [tenant_id: {tenant_id}]")
    statement = select(TenantInstallation).where(
        TenantInstallation.tenant_id == tenant_id
    )
    result = session.exec(statement)
    installations = result.all()
    # TODO: in the future support more than one onboard..
    # {"onboarded": {"github": true, "gitlab": false}"}}
    if installations:
        return JSONResponse({"onboarded": True})
    else:
        return JSONResponse({"onboarded": False})


@router.post("/github", status_code=204)
async def save_github_installation_id(
    request: Request,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> None:
    try:
        # Get the installation_id and action from the request body
        data = await request.json()
        installation_id = data.get("installation_id")
        # TODO - do things with the action (update, etc)
        action = data.get("setup_action")

        # Check if the installation ID already exists for the tenant
        statement = select(TenantInstallation).where(
            TenantInstallation.tenant_id == tenant_id,
            TenantInstallation.bot_id == str(installation_id),
        )
        existing_installation = session.exec(statement).first()
        if existing_installation:
            # TODO: update the installation if needed
            return JSONResponse({"success": True})

        # Create a new TenantInstallation instance and save it in the database
        new_installation = TenantInstallation(
            id=uuid4(), tenant_id=tenant_id, bot_id=str(installation_id), installed=True
        )
        api_key = str(uuid4())
        hashed_api_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        # Save the api key in the secret manager
        secret_manager = SecretManagerFactory.get_secret_manager()
        secret_manager.write_secret(
            secret_name=f"{tenant_id}_{installation_id}",
            secret_value=api_key,
        )
        # Save the api key in the database
        new_installation_api_key = TenantApiKey(
            tenant_id=tenant_id, reference_id=installation_id, key_hash=hashed_api_key
        )
        session.add(new_installation)
        session.add(new_installation_api_key)
        session.commit()
    except Exception as e:
        return JSONResponse({"success": False})
    # Return a success response
    return JSONResponse({"success": True})
