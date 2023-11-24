import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

# This import is required to create the tables
from keep.api.core.dependencies import get_session, verify_bearer_token
from keep.api.models.db.tenant import TenantInstallation
from keep.api.utils.tenant_utils import create_api_key

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
        # action = data.get("setup_action")

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
        create_api_key(
            session,
            tenant_id,
            str(installation_id),
            is_system=True,
            system_description="GitHub application",
            commit=False,
        )  # commit happens after the installation is saved
        session.add(new_installation)
        session.commit()
    except Exception:
        return JSONResponse({"success": False})
    # Return a success response
    return JSONResponse({"success": True})
