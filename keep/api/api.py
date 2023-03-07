import os

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from keep.api.routes import alertsfiles, healthcheck, providers


def get_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(providers.router, prefix="/providers")
    app.include_router(alertsfiles.router, prefix="/alertsfiles")
    app.include_router(healthcheck.router, prefix="/healthcheck")
    return app


def run(app: FastAPI):
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
