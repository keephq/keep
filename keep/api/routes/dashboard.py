from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from keep.api.core.db import create_dashboard as create_dashboard_db
from keep.api.core.db import delete_dashboard as delete_dashboard_db
from keep.api.core.db import get_dashboards as get_dashboards_db
from keep.api.core.db import update_dashboard as update_dashboard_db
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory


class DashboardCreateDTO(BaseModel):
    dashboard_name: str
    dashboard_config: Dict


class DashboardUpdateDTO(BaseModel):
    dashboard_config: Optional[Dict] = None  # Allow partial updates
    dashboard_name: Optional[str] = None


class DashboardResponseDTO(BaseModel):
    id: str
    dashboard_name: str
    dashboard_config: Dict
    created_at: datetime
    updated_at: datetime


class GuestTokenResponse(BaseModel):
    token: str


router = APIRouter()


@router.get("", response_model=List[DashboardResponseDTO])
def read_dashboards(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    dashboards = get_dashboards_db(authenticated_entity.tenant_id)
    return dashboards


@router.post("", response_model=DashboardResponseDTO)
def create_dashboard(
    dashboard_dto: DashboardCreateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    email = authenticated_entity.email
    dashboard = create_dashboard_db(
        tenant_id=authenticated_entity.tenant_id,
        dashboard_name=dashboard_dto.dashboard_name,
        dashboard_config=dashboard_dto.dashboard_config,
        created_by=email,
    )
    return dashboard


@router.put("/{dashboard_id}", response_model=DashboardResponseDTO)
def update_dashboard(
    dashboard_id: str,
    dashboard_dto: DashboardUpdateDTO,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    # update the dashboard in the database
    dashboard = update_dashboard_db(
        tenant_id=authenticated_entity.tenant_id,
        dashboard_id=dashboard_id,
        dashboard_name=dashboard_dto.dashboard_name,
        dashboard_config=dashboard_dto.dashboard_config,
        updated_by=authenticated_entity.email,
    )
    return dashboard


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:dashboards"])
    ),
):
    # delete the dashboard from the database
    dashboard = delete_dashboard_db(authenticated_entity.tenant_id, dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"ok": True}


@router.get("/token", response_model=GuestTokenResponse)
def get_guest_token_route(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    import requests

    SUPERSET_URL = "http://localhost:8088"
    # Authenticate with Superset
    auth_response = requests.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={
            "username": "admin",
            "password": "admin",
            "provider": "db",
        },
    )
    auth_response.raise_for_status()
    access_token = auth_response.json()["access_token"]

    # Step 2: Get the CSRF token
    csrf_response = requests.get(
        f"{SUPERSET_URL}/api/v1/security/csrf_token/",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )
    csrf_response.raise_for_status()
    csrf_token = csrf_response.json()["result"]
    session = csrf_response.cookies.get("session")

    # Step 3: Request guest token from Superset
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-CSRFToken": csrf_token,
    }
    cookies = {"session": session}
    try:
        guest_token_response = requests.post(
            f"{SUPERSET_URL}/api/v1/security/guest_token/",
            headers=headers,
            cookies=cookies,
            json={
                "user": {"username": "apiuser"},
                "resources": [{"type": "dashboard", "id": "2"}],
                "rls": [],  # Add RLS rule
            },
        )
        guest_token_response.raise_for_status()
        guest_token = guest_token_response.json()["token"]
        print("Guest token:", guest_token)
    except requests.exceptions.HTTPError as e:
        error_message = guest_token_response.json()
        print("Error:", error_message)
        if "message" in error_message and "rls" in error_message["message"]:
            print("RLS error:", error_message["message"]["rls"])
        raise e

    if not guest_token:
        raise HTTPException(status_code=500, detail="Failed to generate guest token")
    return GuestTokenResponse(token=guest_token)
