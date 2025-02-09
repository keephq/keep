import logging

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


@router.get("/token", response_model=GuestTokenResponse)
def get_guest_token_route(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:dashboards"])
    ),
):
    import requests

    # Authenticate with Superset
    auth_response = requests.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={
            "username": SUPERSET_USER,
            "password": SUPERSET_PASSWORD,
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
