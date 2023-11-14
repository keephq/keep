import json

from fastapi import APIRouter, Depends, Form, HTTPException
from pusher import Pusher

from keep.api.core.dependencies import get_pusher_client, verify_bearer_token

router = APIRouter()


@router.post("/auth", status_code=200)
def pusher_authentication(
    channel_name=Form(...),
    socket_id=Form(...),
    tenant_id: str = Depends(verify_bearer_token),
    pusher_client: Pusher = Depends(get_pusher_client),
) -> dict:
    """
    Authenticate a user to a private channel

    Args:
        request (Request): The request object
        tenant_id (str, optional): The tenant ID. Defaults to Depends(verify_bearer_token).
        pusher_client (Pusher, optional): Pusher client. Defaults to Depends(get_pusher_client).

    Raises:
        HTTPException: 403 if the user is not allowed to access the channel.

    Returns:
        dict: The authentication response.
    """
    if channel_name == f"private-{tenant_id}":
        auth = pusher_client.authenticate(channel=channel_name, socket_id=socket_id)
        return auth
    raise HTTPException(status_code=403, detail="Forbidden")
