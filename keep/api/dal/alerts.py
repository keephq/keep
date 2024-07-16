import logging
from datetime import datetime
from sqlmodel import Session

from keep.api.core.db import engine
from keep.api.models.db.alert import Alert

logger = logging.getLogger(__name__)


def get_alerts_count(
        tenant_id: str,
) -> int:
    with Session(engine) as session:
        return session.query(Alert).filter(
            Alert.tenant_id == tenant_id,
        ).count()

def get_first_alert_datetime(
        tenant_id: str,
) -> datetime | None:
    with Session(engine) as session:
        first_alert = session.query(Alert).filter(
            Alert.tenant_id == tenant_id,
        ).first()
        if first_alert:
            return first_alert.timestamp
