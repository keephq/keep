import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from keep.api.core.config import config
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

SUPERSET_URL = config("SUPERSET_URL", default="http://localhost:8088")
SUPERSET_USER = config("SUPERSET_USER", default="admin")
SUPERSET_PASSWORD = config("SUPERSET_PASSWORD", default="admin")


class GuestTokenResponse(BaseModel):
    token: str


class Dashboard(BaseModel):
    id: str
    title: str
    url: str
    uuid: Optional[str] = None


class DashboardList(BaseModel):
    dashboards: List[Dashboard]


class SupersetClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token = None
        self.csrf_token = None
        self.session_cookie = None

    def authenticate(self):
        import requests

        # Step 1: Login and get access token
        auth_response = requests.post(
            f"{self.base_url}/api/v1/security/login",
            json={
                "username": self.username,
                "password": self.password,
                "provider": "db",
            },
        )
        auth_response.raise_for_status()
        self.access_token = auth_response.json()["access_token"]

        # Step 2: Get CSRF token
        csrf_response = requests.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        csrf_response.raise_for_status()
        self.csrf_token = csrf_response.json()["result"]
        self.session_cookie = csrf_response.cookies.get("session")

        return self

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-CSRFToken": self.csrf_token,
        }

    def get_cookies(self):
        return {"session": self.session_cookie}

    def get_dashboards(self):
        import requests

        if not self.access_token:
            self.authenticate()

        # First get the list of dashboards
        dashboards_response = requests.get(
            f"{self.base_url}/api/v1/dashboard/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        dashboards_response.raise_for_status()
        dashboards = dashboards_response.json()["result"]

        # For each dashboard, get the embedded data
        for dashboard in dashboards:
            detail_response = requests.get(
                f"{self.base_url}/api/v1/dashboard/{dashboard['id']}/embedded",
                headers=self.get_headers(),
                cookies=self.get_cookies(),
            )
            detail_response.raise_for_status()
            embedded_id = detail_response.json().get("result", {}).get("uuid")
            dashboard["embedded_id"] = embedded_id

        return dashboards

    def get_guest_token(self, dashboard_id: str):
        import requests

        if not self.access_token:
            self.authenticate()

        response = requests.post(
            f"{self.base_url}/api/v1/security/guest_token/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
            json={
                "user": {"username": "apiuser"},
                "resources": [{"type": "dashboard", "id": dashboard_id}],
                "rls": [],
            },
        )
        response.raise_for_status()
        return response.json()["token"]


@router.get("/dashboards", response_model=DashboardList)
def get_dashboards_route(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    """Get all available dashboards from Superset"""
    try:
        client = SupersetClient(SUPERSET_URL, SUPERSET_USER, SUPERSET_PASSWORD)
        dashboards_data = client.get_dashboards()

        dashboards = [
            Dashboard(
                id=dashboard["id"],
                title=dashboard["dashboard_title"],
                url=f"{SUPERSET_URL}/superset/dashboard/{dashboard['id']}",
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
        client = SupersetClient(SUPERSET_URL, SUPERSET_USER, SUPERSET_PASSWORD)
        guest_token = client.get_guest_token(dashboard_id)
        return GuestTokenResponse(token=guest_token)
    except Exception as e:
        logger.error(f"Failed to generate guest token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate guest token")
