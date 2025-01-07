import logging
import os
import time
from importlib import metadata

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from keep.api.core.db import get_api_key

logger = logging.getLogger(__name__)
try:
    KEEP_VERSION = metadata.version("keep")
except Exception:
    KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")


def _extract_identity(request: Request, attribute="email") -> str:
    try:
        token = request.headers.get("Authorization").split(" ")[1]
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        return decoded_token.get(attribute)
    # case api key
    except AttributeError:
        # try api key
        api_key = request.headers.get("x-api-key")
        if not api_key:
            return "anonymous"

        api_key = get_api_key(api_key)
        if api_key:
            return api_key.tenant_id
        return "anonymous"
    except Exception:
        return "anonymous"


class LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        identity = _extract_identity(request, attribute="keep_tenant_id")
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"tenant_id": identity},
        )

        # for debugging purposes, log the payload
        if os.environ.get("LOG_AUTH_PAYLOAD", "false") == "true":
            logger.info(f"Request headers: {request.headers}")

        start_time = time.time()
        request.state.tenant_id = identity
        response = await call_next(request)

        end_time = time.time()
        logger.info(
            f"Request finished: {request.method} {request.url.path} {response.status_code} in {end_time - start_time:.2f}s",
            extra={
                "tenant_id": identity,
                "status_code": response.status_code,
            },
        )
        return response
