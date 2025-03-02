import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.superset_client.superset_client import SupersetClient

router = APIRouter()
logger = logging.getLogger(__name__)

superset_client = SupersetClient()


class GuestTokenResponse(BaseModel):
    token: str


class Dashboard(BaseModel):
    id: str
    title: str
    url: str
    uuid: Optional[str] = None


class DashboardList(BaseModel):
    dashboards: List[Dashboard]


@router.get("/dashboards", response_model=DashboardList)
def get_dashboards_route(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    """Get all available dashboards from Superset"""
    try:
        dashboards_data = superset_client.get_dashboards_by_tenant_id(
            authenticated_entity.tenant_id, should_exist=True
        )

        dashboards = [
            Dashboard(
                id=dashboard["id"],
                title=dashboard["dashboard_title"],
                url=f"{superset_client.base_url}/superset/dashboard/{dashboard['id']}",
                uuid=dashboard.get("embedded_id"),
            )
            for dashboard in dashboards_data
        ]

        return DashboardList(dashboards=dashboards)
    except Exception as e:
        logger.error(f"Failed to fetch dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboards")


@router.get("/token", response_model=GuestTokenResponse)
def get_guest_token_route(
    dashboard_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    """Get a guest token for a specific dashboard"""
    try:
        guest_token = superset_client.get_guest_token(dashboard_id)
        return GuestTokenResponse(token=guest_token)
    except Exception as e:
        logger.error(f"Failed to generate guest token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate guest token")
