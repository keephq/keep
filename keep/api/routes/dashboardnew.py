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
    order: Optional[int] = None
    uuid: Optional[str] = None


class DashboardList(BaseModel):
    dashboards: List[Dashboard]


def extract_order_and_title(full_title):
    """
    Extract the order and title from a full title with the format:
    (order). {name} - {tenant_id}

    Args:
        full_title (str): The full title string

    Returns:
        tuple: (order, title) where order is an integer and title is a string
    """
    # First, split by the last occurrence of " - "
    parts = full_title.rsplit(" - ", 1)

    # Extract the title (everything except the tenant_id)
    title_with_order = parts[0]

    # Split the title to get the order and the actual title
    # Find the first occurrence of ". " to separate order and title
    dot_index = title_with_order.find(". ")

    if dot_index != -1:
        order = int(title_with_order[:dot_index])
        title = title_with_order[dot_index + 2 :]  # Skip the ". " part
    else:
        # Handle case where there might not be a proper order
        order = None
        title = title_with_order

    return order, title


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
        dashboards = []
        for dashboard in dashboards_data:
            dashboard_title = dashboard["dashboard_title"]

            # Extract order and title from the dashboard title
            order, title = extract_order_and_title(dashboard_title)

            # Create dashboard object with extracted title
            dashboards.append(
                Dashboard(
                    id=dashboard["id"],
                    title=title,
                    order=order,
                    url=f"{superset_client.base_url}/superset/dashboard/{dashboard['id']}",
                    uuid=dashboard.get("embedded_id"),
                )
            )

        # Sort dashboards by order
        sorted_dashboards = sorted(
            dashboards, key=lambda d: d.order if d.order is not None else float("inf")
        )
        return DashboardList(dashboards=sorted_dashboards)

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
        guest_token = superset_client.get_guest_token(
            dashboard_id, authenticated_entity.tenant_id
        )
        return GuestTokenResponse(token=guest_token)
    except Exception as e:
        logger.error(f"Failed to generate guest token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate guest token")
