import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.core.config import config
from keep.api.core.dependencies import decode_auth0_token, get_session, verify_customer
from keep.api.models.db.tenant import Tenant, TenantInstallation
from keep.providers.providers_factory import ProvidersFactory
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
    payload: Optional[dict] = Depends(decode_auth0_token),
    session: Session = Depends(get_session),
) -> JSONResponse:
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
        )

    tenant_id = payload.get("keep_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
        )
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
    payload: Optional[dict] = Depends(decode_auth0_token),
    session: Session = Depends(get_session),
) -> None:
    try:
        # Get the authenticated tenant from the dependencies
        tenant_id = payload.get("keep_tenant_id")

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
        session.add(new_installation)
        session.commit()
    except Exception as e:
        return JSONResponse({"success": False})
    # Return a success response
    return JSONResponse({"success": True})
