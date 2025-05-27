from contextlib import asynccontextmanager
import os
import random
import sys
from fastapi import FastAPI
import asyncio
import json
import logging

from event_generator.db import engine, Base, AsyncSessionLocal
from event_generator.models import EventModel
from event_generator.api import event_router
from event_generator.schemas import EventPostBody
from event_generator.settings import config_settings

logging.basicConfig(
    level=config_settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)



async def generate_events(events: list[EventPostBody]):
    """Generate events every EVENT_GENERATOR_INTERVAL seconds."""
    while True:
        for event in events:
            try:
                async with AsyncSessionLocal() as session:
                    event = EventModel(
                        name=event.name,
                        description=event.description,
                        severity=event.severity,
                        environment=event.environment,
                        product_name=event.product_name,
                        service=event.service,
                        operator=event.operator,
                        run_id=event.run_id,
                    )
                    session.add(event)
                    await session.commit()
                    logger.debug(f"Generated event in DB")
            except Exception:
                logger.exception(f"Error generating event")
            finally:
                await session.close()
                await asyncio.sleep(config_settings.EVENT_GENERATOR_INTERVAL)


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
    with open(config_settings.SAMPLE_EVENTS_FILE_PATH, "r") as file:
        events = json.load(file)
        events = [
            EventPostBody(**event) for event in events
        ]
        # shuffle events

    # Start background task
    task = asyncio.create_task(generate_events(events))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app():
    """Create FastAPI app with lifespan and routes."""
    app = FastAPI(
        lifespan=lifespan,
        title="Event Generator",
    )

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
