import logging
import os
from importlib import metadata

import jwt
import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

import keep.api.logging
import keep.api.observability
from keep.api.core.config import AuthenticationType
from keep.api.core.db import get_user
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.logging import CONFIG as logging_config
from keep.api.routes import (
    alerts,
    groups,
    healthcheck,
    mapping,
    preset,
    providers,
    pusher,
    rules,
    settings,
    status,
    users,
    whoami,
    workflows,
)
from keep.event_subscriber.event_subscriber import EventSubscriber
from keep.posthog.posthog import get_posthog_client
from keep.workflowmanager.workflowmanager import WorkflowManager

load_dotenv(find_dotenv())
keep.api.logging.setup()
logger = logging.getLogger(__name__)

HOST = os.environ.get("KEEP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))
SCHEDULER = os.environ.get("SCHEDULER", "true") == "true"
CONSUMER = os.environ.get("CONSUMER", "true") == "true"
AUTH_TYPE = os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
try:
    KEEP_VERSION = metadata.version("keep")
except Exception:
    KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")
POSTHOG_API_ENABLED = os.environ.get("ENABLE_POSTHOG_API", "false") == "true"


class EventCaptureMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.posthog_client = get_posthog_client()
        self.tracer = trace.get_tracer(__name__)

    def _extract_identity(self, request: Request) -> str:
        try:
            token = request.headers.get("Authorization").split(" ")[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            return decoded_token.get("email")
        except Exception:
            return "anonymous"

    async def capture_request(self, request: Request) -> None:
        if POSTHOG_API_ENABLED:
            identity = self._extract_identity(request)
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
        if POSTHOG_API_ENABLED:
            identity = self._extract_identity(request)
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
        if POSTHOG_API_ENABLED:
            with self.tracer.start_as_current_span("flush_posthog_events"):
                logger.info("Flushing Posthog events")
                self.posthog_client.flush()
                logger.info("Posthog events flushed")

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


def get_app(
    auth_type: AuthenticationType = AuthenticationType.NO_AUTH.value,
) -> FastAPI:
    if not os.environ.get("KEEP_API_URL", None):
        os.environ["KEEP_API_URL"] = f"http://{HOST}:{PORT}"
        logger.info(f"Starting Keep with {os.environ['KEEP_API_URL']} as URL")

    app = FastAPI(
        title="Keep API",
        description="Rest API powering https://platform.keephq.dev and friends 🏄‍♀️",
        version="0.1.0",
    )
    app.add_middleware(RawContextMiddleware, plugins=(plugins.RequestIdPlugin(),))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if not os.getenv("DISABLE_POSTHOG", "false") == "true":
        app.add_middleware(EventCaptureMiddleware)
    # app.add_middleware(GZipMiddleware)

    app.include_router(providers.router, prefix="/providers", tags=["providers"])
    app.include_router(healthcheck.router, prefix="/healthcheck", tags=["healthcheck"])
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    app.include_router(settings.router, prefix="/settings", tags=["settings"])
    app.include_router(
        workflows.router, prefix="/workflows", tags=["workflows", "alerts"]
    )
    app.include_router(whoami.router, prefix="/whoami", tags=["whoami"])
    app.include_router(pusher.router, prefix="/pusher", tags=["pusher"])
    app.include_router(status.router, prefix="/status", tags=["status"])
    app.include_router(rules.router, prefix="/rules", tags=["rules"])
    app.include_router(preset.router, prefix="/preset", tags=["preset"])
    app.include_router(groups.router, prefix="/groups", tags=["groups"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(mapping.router, prefix="/mapping", tags=["mapping"])

    # if its single tenant with authentication, add signin endpoint
    logger.info(f"Starting Keep with authentication type: {AUTH_TYPE}")
    # If we run Keep with SINGLE_TENANT auth type, we want to add the signin endpoint
    if AUTH_TYPE == AuthenticationType.SINGLE_TENANT.value:

        @app.post("/signin")
        def signin(body: dict):
            # validate the user/password
            user = get_user(body.get("username"), body.get("password"))

            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"message": "Invalid username or password"},
                )
            # generate a JWT secret
            jwt_secret = os.environ.get("KEEP_JWT_SECRET")
            if not jwt_secret:
                logger.info("missing KEEP_JWT_SECRET environment variable")
                raise HTTPException(status_code=401, detail="Missing JWT secret")
            token = jwt.encode(
                {
                    "email": user.username,
                    "tenant_id": SINGLE_TENANT_UUID,
                    "role": user.role,
                },
                jwt_secret,
                algorithm="HS256",
            )
            # return the token
            return {
                "accessToken": token,
                "tenantId": SINGLE_TENANT_UUID,
                "email": user.username,
                "role": user.role,
            }

    @app.on_event("startup")
    async def on_startup():
        # load all providers into cache
        from keep.providers.providers_factory import ProvidersFactory

        logger.info("Loading providers into cache")
        ProvidersFactory.get_all_providers()
        logger.info("Providers loaded successfully")
        # Start the services
        logger.info("Starting the services")
        # Start the scheduler
        if SCHEDULER:
            logger.info("Starting the scheduler")
            wf_manager = WorkflowManager.get_instance()
            await wf_manager.start()
            logger.info("Scheduler started successfully")
        # Start the consumer
        if CONSUMER:
            logger.info("Starting the consumer")
            event_subscriber = EventSubscriber.get_instance()
            # TODO: there is some "race condition" since if the consumer starts before the server,
            #       and start getting events, it will fail since the server is not ready yet
            #       we should add a "wait" here to make sure the server is ready
            await event_subscriber.start()
            logger.info("Consumer started successfully")
        logger.info("Services started successfully")

    @app.exception_handler(Exception)
    async def catch_exception(request: Request, exc: Exception):
        logging.error(
            f"An unhandled exception occurred: {exc}, Trace ID: {request.state.trace_id}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "message": "An internal server error occurred.",
                "trace_id": request.state.trace_id,
                "error_msg": str(exc),
            },
        )

    @app.middleware("http")
    async def log_middeware(request: Request, call_next):
        logger.info(f"Request started: {request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(
            f"Request finished: {request.method} {request.url.path} {response.status_code}"
        )
        return response

    keep.api.observability.setup(app)

    return app


def run(app: FastAPI):
    logger.info("Starting the uvicorn server")
    # call on starting to create the db and tables
    import keep.api.config

    keep.api.config.on_starting()

    # run the server
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_config=logging_config,
    )
