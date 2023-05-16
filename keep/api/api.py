import os

import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context import context, plugins
from starlette_context.middleware import RawContextMiddleware

from keep.api.core.dependencies import create_db_and_tables
from keep.api.routes import healthcheck, providers, tenant
from keep.contextmanager.contextmanager import ContextManager

load_dotenv(find_dotenv())


async def dispose_context_manager() -> None:
    """Dump context manager after every request."""
    # https://stackoverflow.com/questions/75486472/flask-teardown-request-equivalent-in-fastapi
    yield
    ContextManager.delete_instance()


def get_app() -> FastAPI:
    app = FastAPI(dependencies=[Depends(dispose_context_manager)])
    app.add_middleware(RawContextMiddleware, plugins=(plugins.RequestIdPlugin(),))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(providers.router, prefix="/providers")
    app.include_router(healthcheck.router, prefix="/healthcheck")
    app.include_router(tenant.router, prefix="/tenant")

    @app.on_event("startup")
    def on_startup():
        create_db_and_tables()

    return app


def run(app: FastAPI):
    # https://stackoverflow.com/questions/46827007/runtimeerror-this-event-loop-is-already-running-in-python
    # Shahar: I hate it but that's seem the only workaround..
    import nest_asyncio

    nest_asyncio.apply()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
