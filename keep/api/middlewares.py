import os
import jwt
import time
import logging
from importlib import metadata

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from keep.api.core.db import get_api_key
from keep.posthog.posthog import get_posthog_client

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
    
class PostHogEventCaptureMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.posthog_client = get_posthog_client()
        self.tracer = trace.get_tracer(__name__)

    async def capture_request(self, request: Request) -> None:
        identity = _extract_identity(request)
        with self.tracer.start_as_current_span("capture_request"):
            self.posthog_client.capture(
                identity,
                "request-started",
                {
                    "path": request.url.path,
                    "method": request.method,
                    "keep_version": KEEP_VERSION,
                },
            )

    async def capture_response(self, request: Request, response: Response) -> None:
        identity = _extract_identity(request)
        with self.tracer.start_as_current_span("capture_response"):
            self.posthog_client.capture(
                identity,
                "request-finished",
                {
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "keep_version": KEEP_VERSION,
                },
            )

    async def flush(self):
        with self.tracer.start_as_current_span("flush_posthog_events"):
            logger.debug("Flushing Posthog events")
            self.posthog_client.flush()
            logger.debug("Posthog events flushed")

    async def dispatch(self, request: Request, call_next):
        # Skip OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        # Capture event before request
        await self.capture_request(request)

        response = await call_next(request)

        # Capture event after request
        await self.capture_response(request, response)

        # Perform async tasks or flush events after the request is handled
        await self.flush()
        return response


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
        )
        return response
