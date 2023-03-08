import os
import uuid

import uvicorn
from fastapi import Depends, FastAPI
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context import context, plugins
from starlette_context.middleware import RawContextMiddleware

from keep.api.routes import alertsfiles, providers
from keep.contextmanager.contextmanager import ContextManager


async def dispose_context_manager() -> None:
    """Close current after every request."""
    # https://stackoverflow.com/questions/75486472/flask-teardown-request-equivalent-in-fastapi
    yield
    ContextManager.delete_instance()


def get_app() -> FastAPI:
    app = FastAPI(dependencies=[Depends(dispose_context_manager)])
    middleware = Middleware(
        RawContextMiddleware,
        plugins=(plugins.RequestIdPlugin(), plugins.CorrelationIdPlugin()),
    )
    app.add_middleware(RawContextMiddleware, plugins=(plugins.RequestIdPlugin(),))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(providers.router, prefix="/providers")
    app.include_router(alertsfiles.router, prefix="/alertsfiles")
    return app


def run(app: FastAPI):
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
