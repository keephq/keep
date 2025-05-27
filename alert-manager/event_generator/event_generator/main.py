from contextlib import asynccontextmanager
import os
import random
import sys
from fastapi import FastAPI
import asyncio
import json
import logging

from event_generator.db import engine, Base
from event_generator.api import event_router
from event_generator.schemas import EventPostBody
from event_generator.settings import config_settings

logging.basicConfig(
    level=config_settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def wait_for_mysql_connection(delay=3):
    """Try to connect to MySQL, retrying if necessary."""
    while True:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda conn: None)  # Simple test query
            logger.info("Successfully connected to MySQL.")
            return
        except Exception as e:
            logger.warning(f"MySQL connection attempt failed: {e}")
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event for FastAPI app.

    This function is called when the app starts and stops.
    It creates the database tables and starts the background task.
    """
    # Retry until MySQL is ready
    await wait_for_mysql_connection()
    logger.info("MySQL is ready. Proceeding with app startup.")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


def create_app():
    """Create FastAPI app with lifespan and routes."""
    app = FastAPI(
        lifespan=lifespan,
        title="Event Generator",
    )
    app.state.event_generator_task = None
    app.state.event_index = 0  # only if not already set

    # Include routes
    app.include_router(event_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config_settings.EVENT_GENERATOR_PORT,
        reload=config_settings.DEBUG,
    )
