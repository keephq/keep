import logging
import os

from fastapi import Request
from fastapi.datastructures import FormData
from pusher import Pusher

from keep.api.core.config import config

from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"

PUSHER_ROOT_CA = config("PUSHER_ROOT_CA", default=None)

if PUSHER_ROOT_CA:
    logger.warning("Patching PUSHER root certificate")
    from pusher import requests as pusher_requests

    pusher_requests.CERT_PATH = PUSHER_ROOT_CA


async def extract_generic_body(request: Request) -> dict | bytes | FormData:
    """
    Extracts the body of the request based on the content type.

    Args:
        request (Request): The request object.

    Returns:
        dict | bytes | FormData: The body of the request.
    """
    content_type = request.headers.get("Content-Type")
    if content_type == "application/x-www-form-urlencoded":
        return await request.form()
    elif isinstance(content_type, str) and content_type.startswith(
        "multipart/form-data"
    ):
        return await request.form()
    else:
        try:
            logger.debug("Parsing body as json")
            body = await request.json()
            logger.debug("Parsed body as json")
            return body
        except Exception:
            logger.debug("Failed to parse body as json, returning raw body")
            return await request.body()


def get_pusher_client() -> Pusher | None:
    logger.debug("Getting pusher client")
    pusher_disabled = os.environ.get("PUSHER_DISABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    # Support dedicated internal/private/server pusher host to resolve client/server divergence
    # (e.g. when frontend uses a public reverse proxy path like "/websocket" while backend
    # connects to an internal container address like "keep-websocket-server").
    pusher_host = (
        os.environ.get("PUSHER_HOST_INTERNAL")
        or os.environ.get("PUSHER_HOST_PRIVATE")
        or os.environ.get("PUSHER_HOST_SERVER")
        or os.environ.get("PUSHER_HOST")
    )
    pusher_port_env = (
        os.environ.get("PUSHER_PORT_INTERNAL")
        or os.environ.get("PUSHER_PORT_PRIVATE")
        or os.environ.get("PUSHER_PORT_SERVER")
        or os.environ.get("PUSHER_PORT")
    )
    pusher_ssl_env = (
        os.environ.get("PUSHER_USE_SSL_INTERNAL")
        or os.environ.get("PUSHER_USE_SSL_PRIVATE")
        or os.environ.get("PUSHER_USE_SSL_SERVER")
        or os.environ.get("PUSHER_USE_SSL")
    )
    pusher_app_id = os.environ.get("PUSHER_APP_ID")
    pusher_app_key = os.environ.get("PUSHER_APP_KEY")
    pusher_app_secret = os.environ.get("PUSHER_APP_SECRET")
    if (
        pusher_disabled
        or pusher_app_id is None
        or pusher_app_key is None
        or pusher_app_secret is None
    ):
        logger.debug("Pusher is disabled or missing environment variables")
        return None

    # Handle relative path host (e.g. "/websocket" used by frontend ingress)
    if pusher_host and pusher_host.startswith("/"):
        logger.warning(
            "PUSHER_HOST is configured as a relative path ('%s'). Backend Pusher client requires an absolute host or "
            "PUSHER_HOST_INTERNAL/PUSHER_HOST_PRIVATE. Real-time push notifications are disabled.",
            pusher_host,
        )
        return None

    pusher_use_ssl = False
    if pusher_ssl_env is not None:
        if isinstance(pusher_ssl_env, str):
            pusher_use_ssl = pusher_ssl_env.lower() in ("1", "true", "yes", "on")
        else:
            pusher_use_ssl = bool(pusher_ssl_env)

    pusher_port = int(pusher_port_env) if pusher_port_env else None

    # Normalize host when given as URL, host:port, or host/path
    if pusher_host:
        if "://" in pusher_host:
            parsed = urlparse(pusher_host)
            pusher_host = parsed.hostname
            if parsed.port and not pusher_port:
                pusher_port = parsed.port
            if pusher_ssl_env is None:
                if parsed.scheme in ("https", "wss"):
                    pusher_use_ssl = True
                elif parsed.scheme in ("http", "ws"):
                    pusher_use_ssl = False
        elif "/" in pusher_host or ":" in pusher_host:
            parsed = urlparse(f"//{pusher_host}")
            pusher_host = parsed.hostname
            if parsed.port and not pusher_port:
                pusher_port = parsed.port

    try:
        pusher = Pusher(
            host=pusher_host,
            port=pusher_port,
            app_id=pusher_app_id,
            key=pusher_app_key,
            secret=pusher_app_secret,
            ssl=pusher_use_ssl,
            cluster=os.environ.get("PUSHER_CLUSTER"),
        )
    except ValueError:
        logger.warning(
            "Pusher client could not be initialized due to invalid configuration "
            "(PUSHER_APP_ID must be a numeric string). "
            "Real-time push notifications are disabled.",
            extra={"pusher_app_id": pusher_app_id},
        )
        return None
    logger.debug("Pusher client initialized")
    return pusher
