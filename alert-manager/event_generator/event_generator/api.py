from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from event_generator.db import get_session
from event_generator.models import EventModel
from event_generator.schemas import EventBulkPostBody

event_router = APIRouter()


@event_router.post("/create_event")
async def create_event(events: EventBulkPostBody, session: AsyncSession = Depends(get_session)) -> None:
    db_events = [
            EventModel(**event.dict())
            for event in events.events
    ]

    session.add_all(db_events)
    await session.commit()

