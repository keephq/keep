import logging
import os

from fastapi import HTTPException, Request
from fastapi.datastructures import FormData

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.identitymanager.rbac import Admin as AdminRole

logger = logging.getLogger(__name__)


# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"


def get_sse_authenticated_entity(request: Request) -> AuthenticatedEntity:
    """
    Optional auth for SSE: when AUTH_TYPE is noauth and no credentials are
    provided, return default entity (SINGLE_TENANT_UUID). Otherwise verify
    via the normal pusher-scope verifier.
    """
    auth_type = os.environ.get("AUTH_TYPE", "noauth").lower()
    auth_header = request.headers.get("Authorization") or ""
    token_from_header = auth_header.strip().replace("Bearer ", "", 1) if auth_header else ""
    token_from_query = request.query_params.get("token") or ""
    token = token_from_query or token_from_header or None
    api_key = request.headers.get("X-API-KEY")
    has_creds = bool(token or api_key)
    if auth_type == "noauth" and not has_creds:
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=SINGLE_TENANT_EMAIL,
            role=AdminRole.get_name(),
        )
    verifier = IdentityManagerFactory.get_auth_verifier(["read:pusher"])
    try:
        entity = verifier.authenticate(request, api_key, None, token, None)
        if isinstance(entity, AuthenticatedEntity):
            verifier.authorize(entity)
            return entity
        return entity
    except HTTPException:
        raise
    except Exception:
        logger.exception("SSE auth failed")
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


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
    elif isinstance(content_type, str) and content_type.startswith("multipart/form-data"):
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
