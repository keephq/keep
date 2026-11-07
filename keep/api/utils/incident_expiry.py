from datetime import datetime, timedelta
from typing import Optional


def compute_incident_expired(
    is_terminal: bool,
    latest_alert_timestamp: Optional[datetime],
    creation_time: Optional[datetime],
    timeframe: int,
    max_window: Optional[int],
    now: datetime,
) -> bool:
    if is_terminal:
        return True
    if (
        max_window
        and creation_time is not None
        and now - creation_time > timedelta(seconds=max_window)
    ):
        return True
    if latest_alert_timestamp is not None:
        return latest_alert_timestamp < now - timedelta(seconds=timeframe)
    return False
