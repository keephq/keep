import logging
import os

import jwt
import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

import keep.api.logging
import keep.api.observability
from keep.api.core.db import create_db_and_tables, try_create_single_tenant
from keep.api.core.dependencies import (
    SINGLE_TENANT_UUID,
    verify_api_key,
    verify_bearer_token,
    verify_single_tenant,
)
from keep.api.logging import CONFIG as logging_config
from keep.api.routes import ai, alerts, healthcheck, providers, tenant, workflows
from keep.contextmanager.contextmanager import ContextManager
from keep.posthog.posthog import get_posthog_client

load_dotenv(find_dotenv())
keep.api.logging.setup()
logger = logging.getLogger(__name__)

HOST = os.environ.get("KEEP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))


async def dispose_context_manager() -> None:
    """Dump context manager after every request."""
    # https://stackoverflow.com/questions/75486472/flask-teardown-request-equivalent-in-fastapi
    yield
    ContextManager.delete_instance()


class EventCaptureMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.posthog_client = get_posthog_client()

    def _extract_identity(self, request: Request) -> str:
        try:
            token = request.headers.get("Authorization").split(" ")[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            return decoded_token.get("email")
        except:
            return "anonymous"

    def capture_request(self, request: Request) -> None:
        identity = self._extract_identity(request)
        self.posthog_client.capture(
            identity,
            "request-started",
            {"path": request.url.path, "method": request.method},
        )

    def capture_response(self, request: Request, response: Response) -> None:
        identity = self._extract_identity(request)
        self.posthog_client.capture(
            identity,
            "request-finished",
            {
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
            },
        )

    def flush(self):
        logger.info("Flushing Posthog events")
        self.posthog_client.flush()
        logger.info("Posthog events flushed")

    async def dispatch(self, request: Request, call_next):
        # Skip OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        # Capture event before request
        self.capture_request(request)

        response = await call_next(request)

        # Capture event after request
        self.capture_response(request, response)

        # Perform async tasks or flush events after the request is handled
        self.flush()
        return response


def get_app(multi_tenant: bool = False) -> FastAPI:
    if not os.environ.get("KEEP_API_URL", None):
        os.environ["KEEP_API_URL"] = f"http://{HOST}:{PORT}"
    app = FastAPI(dependencies=[Depends(dispose_context_manager)])
    app.add_middleware(RawContextMiddleware, plugins=(plugins.RequestIdPlugin(),))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(EventCaptureMiddleware)
    multi_tenant = (
        multi_tenant if multi_tenant else os.environ.get("KEEP_MULTI_TENANT", False)
    )

    app.include_router(providers.router, prefix="/providers", tags=["providers"])
    app.include_router(healthcheck.router, prefix="/healthcheck", tags=["healthcheck"])
    app.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
    app.include_router(ai.router, prefix="/ai", tags=["ai"])
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    app.include_router(
        workflows.router, prefix="/workflows", tags=["workflows", "alerts"]
    )

    @app.on_event("startup")
    def on_startup():
        create_db_and_tables()
        if not multi_tenant:
            # When running in single tenant mode, we want to override the secured endpoints
            app.dependency_overrides[verify_api_key] = verify_single_tenant
            app.dependency_overrides[verify_bearer_token] = verify_single_tenant
            try_create_single_tenant(SINGLE_TENANT_UUID)

    keep.api.observability.setup(app)

    if os.environ.get("USE_NGROK"):
        from pyngrok import ngrok

        public_url = ngrok.connect(PORT).public_url
        logger.info(f"ngrok tunnel: {public_url}")
        os.environ["KEEP_API_URL"] = public_url

    return app


def run(app: FastAPI):
    # https://stackoverflow.com/questions/46827007/runtimeerror-this-event-loop-is-already-running-in-python
    # Shahar: I hate it but that's seem the only workaround..
    import nest_asyncio

    nest_asyncio.apply()
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_config=logging_config,
    )
