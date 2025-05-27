import asyncio
import json
import logging
from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from event_generator.schemas import EventPostBody
from event_generator.settings import config_settings

from event_generator.db import get_session
from event_generator.models import EventModel
from event_generator.schemas import EventBulkPostBody
from event_generator.db import AsyncSessionLocal

logger = logging.getLogger(__name__)
event_router = APIRouter()

async def generate_events(events: list[EventPostBody], app, start_index=0):
    """Generate events every X seconds, resume from index, and loop forever."""
    index = start_index
    total_events = len(events)

    while True:
        event = events[index]
        try:
            async with AsyncSessionLocal() as session:
                db_event = EventModel(**event.dict())
                session.add(db_event)
                await session.commit()
                logger.debug(f"Generated event at index {index}")
        except Exception:
            logger.exception("Error generating event")
        finally:
            await session.close()

        # Update the index and store it in app.state
        index = (index + 1) % total_events
        app.state.event_index = index
        await asyncio.sleep(config_settings.EVENT_GENERATOR_INTERVAL)


@event_router.post("/create_event")
async def create_event(events: EventBulkPostBody, session: AsyncSession = Depends(get_session)) -> None:
    db_events = [
            EventModel(**event.dict())
            for event in events.events
    ]

    session.add_all(db_events)
    await session.commit()


@event_router.post("/start")
async def start_event_generation(request: Request):
    app = request.app
    if app.state.event_generator_task and not app.state.event_generator_task.done():
        return JSONResponse(status_code=400, content={"message": "Event generation is already running."})

    with open(config_settings.SAMPLE_EVENTS_FILE_PATH, "r") as file:
        events_data = json.load(file)
        events = [EventPostBody(**event) for event in events_data]

    start_index = getattr(app.state, "event_index", 0)
    task = asyncio.create_task(generate_events(events, app, start_index))
    app.state.event_generator_task = task
    logger.info(f"Started event generation from index {start_index}.")
    return {"message": f"Event generation started from index {start_index}."}

@event_router.post("/stop")
async def stop_event_generation(request: Request):
    app = request.app
    task = app.state.event_generator_task
    if not task or task.done():
        return JSONResponse(status_code=400, content={"message": "Event generation is not running."})

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Event generation task cancelled.")
    app.state.event_generator_task = None
    return {"message": f"Event generation stopped at index {app.state.event_index}."}

