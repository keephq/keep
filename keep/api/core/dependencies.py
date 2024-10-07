import logging
import os

from fastapi import Request
from fastapi.datastructures import FormData
from pusher import Pusher

logger = logging.getLogger(__name__)


# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"


async def extract_generic_body(request: Request) -> dict | bytes | FormData:
    """
    Extracts the body of the request based on the content type.

    Args:
        request (Request): The request object.

    Returns:
        dict | bytes | FormData: The body of the request.
    """
    content_type = request.headers.get("Content-Type")
    if content_type == "application/json":
        return await request.json()
    elif content_type == "application/x-www-form-urlencoded":
        return await request.form()
    else:
        return await request.body()


def get_pusher_client() -> Pusher | None:
    if os.environ.get("PUSHER_DISABLED", "false") == "true":
        return None

    # TODO: defaults on open source no docker
    return Pusher(
        host=os.environ.get("PUSHER_HOST"),
        port=(
            int(os.environ.get("PUSHER_PORT"))
            if os.environ.get("PUSHER_PORT")
            else None
        ),
        app_id=os.environ.get("PUSHER_APP_ID"),
        key=os.environ.get("PUSHER_APP_KEY"),
        secret=os.environ.get("PUSHER_APP_SECRET"),
        ssl=False if os.environ.get("PUSHER_USE_SSL", False) is False else True,
        cluster=os.environ.get("PUSHER_CLUSTER"),
    )
