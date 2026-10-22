"""Opt-in source-time admission, using the existing alert history and cursor.

PostgreSQL session locks deliberately survive the ingest pipeline's commits.
They serialize a single tenant/fingerprint, including first arrivals, through
workflow admission. They do not make an external notification exactly-once.
"""

import hashlib
import os
from contextlib import contextmanager
from datetime import timezone

from dateutil.parser import isoparse
from sqlalchemy import text
from sqlmodel import Session, select

from keep.api.models.db.alert import Alert, LastAlert

SOURCE_ORDERING_RESERVED_FIELDS = frozenset(
    {"fingerprint", "event_id", "sourceEventOrdering"}
)


def enabled(provider_type):
    configured = os.environ.get("KEEP_SOURCE_EVENT_ORDERING_PROVIDERS", "").split(",")
    # Only CloudWatch currently promises that lastReceived is its state change time.
    return provider_type == "cloudwatch" and provider_type in configured


def source_ordered_event_id(event):
    """Use the persisted admission ID, never an enrichment overlay, for comparisons."""
    context = getattr(event, "sourceEventOrdering", None)
    if isinstance(context, dict) and context.get("accepted") is True:
        identity = context.get("eventId")
        if isinstance(identity, str) and identity:
            return identity
    return None


def workflow_enrichments(event, enrichments):
    """Keep admission identity/context reserved at initial dispatch and retries.

    Already queued ordered events retain protection if the feature is later
    disabled. Legacy events without an admission context keep their old merge.
    """
    context = getattr(event, "sourceEventOrdering", None)
    if not isinstance(context, dict) or type(context.get("accepted")) is not bool:
        return enrichments
    return {
        field: value
        for field, value in enrichments.items()
        if field not in SOURCE_ORDERING_RESERVED_FIELDS
    }


def _source_time(event):
    value = isoparse(event["lastReceived"])
    if value.tzinfo is None:
        raise ValueError("Source event ordering requires a timezone-aware timestamp")
    return value.astimezone(timezone.utc)


def source_event_decision(incoming, previous):
    source_time = _source_time(incoming)
    result = {
        "accepted": True,
        "reason": "accepted",
        "recoveryEligible": False,
        "sourceTime": source_time.isoformat(),
        "episodeFiringObserved": False,
    }
    if previous:
        previous_source = dict(previous)
        previous_source["lastReceived"] = previous.get("sourceEventOrdering", {}).get(
            "sourceTime", previous["lastReceived"]
        )
        previous_time = _source_time(previous_source)
        if source_time < previous_time:
            result.update(accepted=False, reason="older_source_event")
        elif source_time == previous_time:
            reason = (
                "duplicate_source_event"
                if incoming.get("status") == previous.get("status")
                else "conflicting_source_time"
            )
            result.update(accepted=False, reason=reason)
        prior_firing = (
            previous.get("status") == "firing"
            or previous.get("sourceEventOrdering", {}).get("episodeFiringObserved")
            is True
        )
    else:
        prior_firing = False
    if result["accepted"]:
        result["recoveryEligible"] = (
            incoming.get("status") == "resolved" and prior_firing
        )
        result["episodeFiringObserved"] = incoming.get("status") == "firing" or (
            incoming.get("status") != "resolved" and prior_firing
        )
    return result


def current_alert(session, tenant_id, fingerprint):
    return session.exec(
        select(Alert)
        .join(LastAlert, LastAlert.alert_id == Alert.id)
        .where(LastAlert.tenant_id == tenant_id, LastAlert.fingerprint == fingerprint)
    ).first()


def advance_source_cursor(session, tenant_id, alert):
    """Advance an admitted source event while holding its fingerprint lock.

    Ingestion clocks may differ between workers. Their order must not override
    the source-time admission decision, and their values are kept unchanged.
    """
    cursor = session.exec(
        select(LastAlert).where(
            LastAlert.tenant_id == tenant_id, LastAlert.fingerprint == alert.fingerprint
        )
    ).first()
    if cursor is None:
        cursor = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            alert_id=alert.id,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_hash=alert.alert_hash,
        )
    else:
        cursor.alert_id = alert.id
        cursor.timestamp = alert.timestamp
        cursor.alert_hash = alert.alert_hash
    session.add(cursor)
    session.commit()


@contextmanager
def serialized_source_event(engine, tenant_id, fingerprint):
    if engine.dialect.name != "postgresql":
        raise ValueError("Source event ordering currently requires PostgreSQL")
    identity = f"{len(tenant_id)}:{tenant_id}:{fingerprint}".encode()
    lock_id = int.from_bytes(hashlib.sha256(identity).digest()[:8], "big", signed=True)
    # Binding the session to this connection retains the session-level advisory
    # lock across the existing ingest commits without holding a second pool slot.
    with engine.connect() as connection:
        acquired = False
        try:
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            acquired = True
            connection.commit()
            with Session(bind=connection, expire_on_commit=False) as session:
                yield session
        finally:
            connection.rollback()
            if acquired:
                try:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id}
                    )
                    connection.commit()
                except Exception:
                    # A pooled connection must never retain a session lock.
                    connection.invalidate()
                    raise
