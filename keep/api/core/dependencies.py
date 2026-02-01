import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import Request
from fastapi.datastructures import FormData
from pusher import Pusher

from keep.api.core.config import config

logger = logging.getLogger(__name__)

# Dev defaults (single-tenant mode)
SINGLE_TENANT_UUID = config("SINGLE_TENANT_UUID", default="keep")
SINGLE_TENANT_EMAIL = config("SINGLE_TENANT_EMAIL", default="admin@keephq")

PUSHER_ROOT_CA = config("PUSHER_ROOT_CA", default=None)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning("Invalid int for %s: %r", name, val)
        return default


def _patch_pusher_root_ca_if_needed() -> None:
    """
    Patch pusher's requests CERT_PATH if PUSHER_ROOT_CA is provided.
    Done lazily (not at import-time) to avoid global side effects during imports.
    """
    if not PUSHER_ROOT_CA:
        return

    ca_path = Path(PUSHER_ROOT_CA)
    if not ca_path.exists() or not ca_path.is_file():
        logger.error("PUSHER_ROOT_CA path does not exist or is not a file: %s", ca_path)
        return

    logger.warning("Patching PUSHER root certificate (custom CA)")
    from pusher import requests as pusher_requests  # import locally on purpose

    pusher_requests.CERT_PATH = str(ca_path)


async def extract_generic_body(request: Request) -> Union[dict, bytes, FormData, Any]:
    """
    Extract request body based on Content-Type.

    - form-url-encoded / multipart => FormData
    - otherwise attempts JSON
    - falls back to raw bytes
    """
    content_type = request.headers.get("Content-Type", "")
    mime = content_type.split(";", 1)[0].strip().lower()

    if mime in {"application/x-www-form-urlencoded", "multipart/form-data"}:
        return await request.form()

    # JSON or unknown: try JSON first
    try:
        logger.debug("Parsing body as JSON (content-type=%r)", content_type)
        return await request.json()
    except Exception as e:
        logger.debug("Failed to parse JSON body; returning raw bytes (%s)", type(e).__name__)
        return await request.body()


def get_pusher_client() -> Optional[Pusher]:
    """
    Build a Pusher client if enabled and configured; otherwise return None.
    """
    logger.debug("Getting pusher client")

    if _env_bool("PUSHER_DISABLED", default=False):
        logger.debug("Pusher disabled via env")
        return None

    pusher_app_id = os.environ.get("PUSHER_APP_ID")
    pusher_app_key = os.environ.get("PUSHER_APP_KEY")
    pusher_app_secret = os.environ.get("PUSHER_APP_SECRET")

    if not pusher_app_id or not pusher_app_key or not pusher_app_secret:
        logger.debug("Pusher missing required env vars (APP_ID/APP_KEY/APP_SECRET)")
        return None

    _patch_pusher_root_ca_if_needed()

    pusher_host = os.environ.get("PUSHER_HOST")
    pusher_port = _env_int("PUSHER_PORT", default=None)
    pusher_ssl = _env_bool("PUSHER_USE_SSL", default=True)
    pusher_cluster = os.environ.get("PUSHER_CLUSTER")

    client = Pusher(
        host=pusher_host,
        port=pusher_port,
        app_id=pusher_app_id,
        key=pusher_app_key,
        secret=pusher_app_secret,
        ssl=pusher_ssl,
        cluster=pusher_cluster,
    )

    logger.debug("Pusher client initialized (host=%r port=%r ssl=%r)", pusher_host, pusher_port, pusher_ssl)
    return client