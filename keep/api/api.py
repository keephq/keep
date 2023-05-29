import logging
import os

import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI
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
from keep.api.routes import ai, healthcheck, providers, tenant
from keep.contextmanager.contextmanager import ContextManager

load_dotenv(find_dotenv())
keep.api.logging.setup()
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))


async def dispose_context_manager() -> None:
    """Dump context manager after every request."""
    # https://stackoverflow.com/questions/75486472/flask-teardown-request-equivalent-in-fastapi
    yield
    ContextManager.delete_instance()


def get_app(multi_tenant: bool = False) -> FastAPI:
    app = FastAPI(dependencies=[Depends(dispose_context_manager)])
    app.add_middleware(RawContextMiddleware, plugins=(plugins.RequestIdPlugin(),))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(providers.router, prefix="/providers", tags=["providers"])
    app.include_router(healthcheck.router, prefix="/healthcheck", tags=["healthcheck"])
    app.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
    app.include_router(ai.router, prefix="/ai", tags=["ai"])

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

    return app


def run(app: FastAPI):
    # https://stackoverflow.com/questions/46827007/runtimeerror-this-event-loop-is-already-running-in-python
    # Shahar: I hate it but that's seem the only workaround..
    import nest_asyncio

    nest_asyncio.apply()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_config=logging_config,
    )
