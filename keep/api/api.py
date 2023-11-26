import logging
import os
import threading
import time

import jwt
import requests
import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context import plugins
from starlette_context.middleware import RawContextMiddleware

import keep.api.logging
import keep.api.observability
from keep.api.core.config import AuthenticationType
from keep.api.core.db import create_db_and_tables, get_user, try_create_single_tenant
from keep.api.core.dependencies import (
    SINGLE_TENANT_UUID,
    get_user_email,
    get_user_email_single_tenant,
    verify_api_key,
    verify_api_key_single_tenant,
    verify_bearer_token,
    verify_bearer_token_single_tenant,
    verify_token_or_key,
    verify_token_or_key_single_tenant,
)
from keep.api.logging import CONFIG as logging_config
from keep.api.routes import (
    ai,
    alerts,
    healthcheck,
    providers,
    pusher,
    settings,
    status,
    tenant,
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


class EventCaptureMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.posthog_client = get_posthog_client()

    def _extract_identity(self, request: Request) -> str:
        try:
            token = request.headers.get("Authorization").split(" ")[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            return decoded_token.get("email")
        except Exception:
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
    app.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
    app.include_router(ai.router, prefix="/ai", tags=["ai"])
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    app.include_router(settings.router, prefix="/settings", tags=["settings"])
    app.include_router(
        workflows.router, prefix="/workflows", tags=["workflows", "alerts"]
    )
    app.include_router(whoami.router, prefix="/whoami", tags=["whoami"])
    app.include_router(pusher.router, prefix="/pusher", tags=["pusher"])
    app.include_router(status.router, prefix="/status", tags=["status"])

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
                raise HTTPException(status_code=401, detail="Missing JWT secret")
            token = jwt.encode(
                {
                    "email": user.username,
                    "tenant_id": SINGLE_TENANT_UUID,
                },
                jwt_secret,
                algorithm="HS256",
            )
            # return the token
            return {
                "accessToken": token,
                "tenantId": SINGLE_TENANT_UUID,
                "email": user.username,
            }

    from fastapi import BackgroundTasks

    @app.post("/start-services")
    async def start_services(background_tasks: BackgroundTasks):
        logger.info("Starting the internal services")
        if SCHEDULER:
            logger.info("Starting the scheduler")
            wf_manager = WorkflowManager.get_instance()
            background_tasks.add_task(wf_manager.start)
            logger.info("Scheduler started successfully")

        if CONSUMER:
            logger.info("Starting the consumer")
            event_subscriber = EventSubscriber.get_instance()
            background_tasks.add_task(event_subscriber.start)
            logger.info("Consumer started successfully")

        return {"status": "Services are starting in the background"}

    @app.on_event("startup")
    async def on_startup():
        if not os.environ.get("SKIP_DB_CREATION", "false") == "true":
            create_db_and_tables()

        # When running in mode other than multi tenant auth, we want to override the secured endpoints
        if AUTH_TYPE != AuthenticationType.MULTI_TENANT.value:
            app.dependency_overrides[verify_api_key] = verify_api_key_single_tenant
            app.dependency_overrides[
                verify_bearer_token
            ] = verify_bearer_token_single_tenant
            app.dependency_overrides[get_user_email] = get_user_email_single_tenant
            app.dependency_overrides[
                verify_token_or_key
            ] = verify_token_or_key_single_tenant
            try_create_single_tenant(SINGLE_TENANT_UUID)

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

    keep.api.observability.setup(app)

    if os.environ.get("USE_NGROK", "false") == "true":
        from pyngrok import ngrok

        public_url = ngrok.connect(PORT).public_url
        logger.info(f"ngrok tunnel: {public_url}")
        os.environ["KEEP_API_URL"] = public_url

    return app


def run_services_after_app_is_up():
    """Waits until the server is up and than invoking the 'start-services' endpoint to start the internal services"""
    logger.info("Waiting for the server to be ready")
    _wait_for_server_to_be_ready()
    logger.info("Server is ready, starting the internal services")
    # start the internal services
    try:
        # the internal services are always on localhost
        response = requests.post(f"http://localhost:{PORT}/start-services")
        response.raise_for_status()
        logger.info("Internal services started successfully")
    except Exception as e:
        logger.info("Failed to start internal services")
        raise e


def _is_server_ready() -> bool:
    # poll localhost to see if the server is up
    try:
        # we are using hardcoded "localhost" to avoid problems where we start Keep on platform such as CloudRun where we have more than one instance
        response = requests.get(f"http://localhost:{PORT}/healthcheck", timeout=1)
        response.raise_for_status()
        return True
    except Exception:
        return False


def _wait_for_server_to_be_ready():
    """Wait until the server is up by polling localhost"""
    start_time = time.time()
    while True:
        if _is_server_ready():
            return True
        if time.time() - start_time >= 60:
            raise TimeoutError("Server is not ready after 60 seconds.")
        else:
            logger.warning("Server is not ready yet, retrying in 1 second...")
        time.sleep(1)


def run(app: FastAPI):
    # We want to start all internal services (workflowmanager, eventsubscriber, etc) only after the server is up
    # so we init a thread that will wait for the server to be up and then start the internal services
    logger.info("Starting the run services thread")
    thread = threading.Thread(target=run_services_after_app_is_up)
    thread.start()
    logger.info("Starting the uvicorn server")
    # run the server
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_config=logging_config,
    )
