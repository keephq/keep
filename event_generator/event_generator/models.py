import datetime
from sqlalchemy import Column, String, TIMESTAMP
import uuid

from event_generator.db import Base


class EventModel(Base):
    __tablename__ = "monitoring_events"

    id = Column(String(36), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    severity = Column(String(10), nullable=True)
    environment = Column(String(50), nullable=True)
    product_name = Column(String(50), nullable=True)
    service = Column(String(50), nullable=True)
    operator = Column(String(50), nullable=True)
    run_id = Column(String(50), nullable=True)
    ts = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.UTC))
