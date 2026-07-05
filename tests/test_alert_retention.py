from datetime import datetime, timedelta

from keep.api.core.db import delete_alerts_by_retention
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.alert import (
    Alert,
    AlertToIncident,
    LastAlert,
    LastAlertToIncident,
)
from keep.api.models.db.incident import Incident


def _create_alert(db_session, fingerprint, timestamp):
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={"name": fingerprint, "fingerprint": fingerprint},
        fingerprint=fingerprint,
        timestamp=timestamp,
    )
    db_session.add(alert)
    db_session.commit()
    return alert


def _create_last_alert(db_session, alert):
    last_alert = LastAlert(
        tenant_id=SINGLE_TENANT_UUID,
        fingerprint=alert.fingerprint,
        alert_id=alert.id,
        timestamp=alert.timestamp,
        first_timestamp=alert.timestamp,
    )
    db_session.add(last_alert)
    db_session.commit()
    return last_alert


def _create_incident(db_session):
    incident = Incident(
        tenant_id=SINGLE_TENANT_UUID,
        user_generated_name="test-incident",
        user_summary="test",
        generated_summary="test",
    )
    db_session.add(incident)
    db_session.commit()
    return incident


def test_delete_alerts_by_retention_purges_old_alerts(db_session):
    incident = _create_incident(db_session)
    old_timestamp = datetime.utcnow() - timedelta(days=100)

    for i in range(3):
        alert = _create_alert(db_session, f"old-{i}", old_timestamp)
        _create_last_alert(db_session, alert)
        db_session.add(
            AlertToIncident(
                tenant_id=SINGLE_TENANT_UUID,
                alert_id=alert.id,
                incident_id=incident.id,
            )
        )
        db_session.add(
            LastAlertToIncident(
                tenant_id=SINGLE_TENANT_UUID,
                fingerprint=alert.fingerprint,
                incident_id=incident.id,
            )
        )
        db_session.commit()

    for i in range(2):
        alert = _create_alert(db_session, f"fresh-{i}", datetime.utcnow())
        _create_last_alert(db_session, alert)

    purge_before = datetime.utcnow() - timedelta(days=30)
    deleted = delete_alerts_by_retention(
        SINGLE_TENANT_UUID, purge_before, batch_size=2, session=db_session
    )

    assert deleted == 3
    remaining_alerts = db_session.query(Alert).all()
    assert sorted(alert.fingerprint for alert in remaining_alerts) == [
        "fresh-0",
        "fresh-1",
    ]
    remaining_last_alerts = db_session.query(LastAlert).all()
    assert sorted(last_alert.fingerprint for last_alert in remaining_last_alerts) == [
        "fresh-0",
        "fresh-1",
    ]
    assert db_session.query(AlertToIncident).count() == 0
    assert db_session.query(LastAlertToIncident).count() == 0


def test_delete_alerts_by_retention_keeps_active_fingerprint(db_session):
    old_alert = _create_alert(
        db_session, "service-down", datetime.utcnow() - timedelta(days=100)
    )
    fresh_alert = _create_alert(db_session, "service-down", datetime.utcnow())
    _create_last_alert(db_session, fresh_alert)
    old_alert_id = old_alert.id
    fresh_alert_id = fresh_alert.id

    purge_before = datetime.utcnow() - timedelta(days=30)
    deleted = delete_alerts_by_retention(
        SINGLE_TENANT_UUID, purge_before, session=db_session
    )

    assert deleted == 1
    assert old_alert_id != fresh_alert_id
    remaining_alerts = db_session.query(Alert).all()
    assert [alert.id for alert in remaining_alerts] == [fresh_alert_id]
    remaining_last_alerts = db_session.query(LastAlert).all()
    assert [last_alert.fingerprint for last_alert in remaining_last_alerts] == [
        "service-down"
    ]


def test_delete_alerts_by_retention_removes_soft_deleted_incident_links(db_session):
    incident = _create_incident(db_session)
    alert = _create_alert(db_session, "stale", datetime.utcnow() - timedelta(days=100))
    _create_last_alert(db_session, alert)
    db_session.add(
        LastAlertToIncident(
            tenant_id=SINGLE_TENANT_UUID,
            fingerprint=alert.fingerprint,
            incident_id=incident.id,
            deleted_at=datetime.utcnow() - timedelta(days=50),
        )
    )
    db_session.commit()

    purge_before = datetime.utcnow() - timedelta(days=30)
    deleted = delete_alerts_by_retention(
        SINGLE_TENANT_UUID, purge_before, session=db_session
    )

    assert deleted == 1
    assert db_session.query(Alert).count() == 0
    assert db_session.query(LastAlert).count() == 0
    assert db_session.query(LastAlertToIncident).count() == 0


def test_delete_alerts_by_retention_noop_when_nothing_expired(db_session):
    alert = _create_alert(db_session, "fresh", datetime.utcnow())
    _create_last_alert(db_session, alert)

    purge_before = datetime.utcnow() - timedelta(days=30)
    deleted = delete_alerts_by_retention(
        SINGLE_TENANT_UUID, purge_before, session=db_session
    )

    assert deleted == 0
    assert db_session.query(Alert).count() == 1
    assert db_session.query(LastAlert).count() == 1
