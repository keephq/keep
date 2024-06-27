from datetime import datetime, timezone


def utcnow():
    return datetime.now(tz=timezone.utc)
