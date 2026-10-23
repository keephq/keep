"""
Test for Keep Provider time_delta filtering bug.
This test reproduces the issue described in https://github.com/keephq/keep/issues/5180
"""

import datetime
import pytest
import time
import uuid
from datetime import timezone, timedelta
from freezegun import freeze_time

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.alert import Alert, LastAlert
from keep.api.models.alert import AlertStatus
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.providers.keep_provider.keep_provider import KeepProvider
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig


def _create_valid_event(d, lastReceived=None):
    """Helper function to create a valid event similar to conftest.py"""
    event = {
        "id": str(uuid.uuid4()),
        "name": "some-test-event",
        "status": "firing",
        "lastReceived": (
            str(lastReceived)
            if lastReceived
            else datetime.datetime.now(tz=timezone.utc).isoformat()
        ),
    }
    event.update(d)
    return event


def test_keep_provider_time_delta_filtering_bug(db_session):
    """
    Test that reproduces the time_delta filtering bug.
    
    This test verifies that when using Keep Provider with version 2 and time_delta,
    only alerts within the specified timeframe are returned, not all alerts.
    """
    # Setup context
    tenant_id = SINGLE_TENANT_UUID
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=None
    )
    
    # Create KeepProvider instance
    provider_config = ProviderConfig(authentication={})
    provider = KeepProvider(
        context_manager=context_manager,
        provider_id="test-keep",
        config=provider_config
    )
    
    # Create alerts with different timestamps
    now = datetime.datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)  # 2 hours ago
    recent_time = now - timedelta(seconds=30)  # 30 seconds ago
    
    # Create alert details similar to conftest.py setup_alerts
    alert_details = [
        {
            "source": ["test"],
            "status": AlertStatus.FIRING.value,
            "lastReceived": old_time.isoformat(),
            "fingerprint": "old-alert-fingerprint",
            "id": "old-alert"
        },
        {
            "source": ["test"],
            "status": AlertStatus.FIRING.value,
            "lastReceived": recent_time.isoformat(),
            "fingerprint": "recent-alert-fingerprint",
            "id": "recent-alert"
        }
    ]
    
    # Create Alert objects
    alerts = []
    for detail in alert_details:
        # Create timestamps from lastReceived
        timestamp = datetime.datetime.fromisoformat(detail["lastReceived"].replace('Z', '+00:00'))
        
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event(detail, detail["lastReceived"]),
            fingerprint=detail["fingerprint"],
            timestamp=timestamp
        )
        alerts.append(alert)
    
    # Add alerts to database
    db_session.add_all(alerts)
    db_session.commit()
    
    # Create LastAlert entries
    last_alerts = []
    for alert in alerts:
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        last_alerts.append(last_alert)
    
    db_session.add_all(last_alerts)
    db_session.commit()
    
    # Test with time_delta of approximately 1 minute (0.000694445 days)
    # This should only return the recent alert, not the old one
    time_delta_1_minute = 0.000694445
    
    # Query using Keep Provider version 2 (which uses SearchEngine)
    with freeze_time(now):
        results = provider._query(
            version=2,
            filter="status == 'firing'",
            time_delta=time_delta_1_minute,
            limit=10000
        )
    
    # This should fail because the bug causes all alerts to be returned
    # instead of just the ones within the time_delta
    assert len(results) == 1, f"Expected 1 alert within time_delta, but got {len(results)}"
    
    # Verify it's the recent alert
    assert results[0].id == "recent-alert"


def test_keep_provider_time_delta_filtering_version_1(db_session):
    """
    Test that version 1 of Keep Provider correctly filters by time_delta.
    This should work correctly as it uses get_alerts_with_filters directly.
    """
    # This test is simpler since we're testing version 1 which should work
    from keep.api.core.db import get_alerts_with_filters
    
    tenant_id = SINGLE_TENANT_UUID
    
    # Create alerts with different timestamps  
    now = datetime.datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)  # 2 hours ago
    recent_time = now - timedelta(seconds=30)  # 30 seconds ago
    
    # Create Alert objects directly
    alerts = []
    
    old_alert = Alert(
        tenant_id=tenant_id,
        provider_type="test",
        provider_id="test",
        event=_create_valid_event({
            "id": "old-alert-v1",
            "status": AlertStatus.FIRING.value,
            "lastReceived": old_time.isoformat(),
        }),
        fingerprint="old-alert-v1-fingerprint",
        timestamp=old_time
    )
    
    recent_alert = Alert(
        tenant_id=tenant_id,
        provider_type="test", 
        provider_id="test",
        event=_create_valid_event({
            "id": "recent-alert-v1",
            "status": AlertStatus.FIRING.value,
            "lastReceived": recent_time.isoformat(),
        }),
        fingerprint="recent-alert-v1-fingerprint",
        timestamp=recent_time
    )
    
    alerts = [old_alert, recent_alert]
    
    # Add alerts to database
    db_session.add_all(alerts)
    db_session.commit()
    
    # Create LastAlert entries (required by get_alerts_with_filters)
    last_alerts = []
    for alert in alerts:
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        last_alerts.append(last_alert)
    
    db_session.add_all(last_alerts)
    db_session.commit()
    
    # Test using get_alerts_with_filters directly (version 1 approach)
    time_delta_1_minute = 0.000694445
    
    with freeze_time(now):
        filtered_alerts = get_alerts_with_filters(
            tenant_id=tenant_id,
            filters=None,  # Test just time_delta filtering without additional filters
            time_delta=time_delta_1_minute
        )
    
    # This should work correctly - only return recent alert
    assert len(filtered_alerts) == 1, f"Expected 1 alert within time_delta, but got {len(filtered_alerts)}"
    assert filtered_alerts[0].event["id"] == "recent-alert-v1" 

def test_keep_provider_timerange_sub_day_window(db_session):
    """
    A timerange shorter than 24h must not be truncated away.

    _calculate_time_delta returns days, so a two-minute window is ~0.00139.
    Casting that to int() gives 0, and both query paths treat 0 as "no time
    filter" - the query then returns all of history rather than the window
    that was asked for. That is worse than an error, because a workflow built
    on it silently sees stale alerts as current.
    """
    tenant_id = SINGLE_TENANT_UUID
    context_manager = ContextManager(tenant_id=tenant_id, workflow_id=None)
    provider = KeepProvider(
        context_manager=context_manager,
        provider_id="test-keep-timerange",
        config=ProviderConfig(authentication={}),
    )

    now = datetime.datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)
    recent_time = now - timedelta(seconds=30)

    alert_details = [
        ("old-alert-timerange", "old-alert-timerange-fingerprint", old_time),
        ("recent-alert-timerange", "recent-alert-timerange-fingerprint", recent_time),
    ]

    alerts = [
        Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event(
                {
                    "id": alert_id,
                    "source": ["test"],
                    "status": AlertStatus.FIRING.value,
                    "lastReceived": ts.isoformat(),
                    "fingerprint": fingerprint,
                },
                ts.isoformat(),
            ),
            fingerprint=fingerprint,
            timestamp=ts,
        )
        for alert_id, fingerprint, ts in alert_details
    ]
    db_session.add_all(alerts)
    db_session.commit()

    db_session.add_all(
        [
            LastAlert(
                tenant_id=tenant_id,
                fingerprint=alert.fingerprint,
                timestamp=alert.timestamp,
                first_timestamp=alert.timestamp,
                alert_id=alert.id,
            )
            for alert in alerts
        ]
    )
    db_session.commit()

    # A two-minute window ending now. Only the 30-second-old alert falls in it.
    timerange = {
        "from": (now - timedelta(minutes=2)).isoformat(),
        "to": now.isoformat(),
    }

    with freeze_time(now):
        results = provider._query(
            version=2,
            filter="status == 'firing'",
            timerange=timerange,
            limit=10000,
        )

    assert len(results) == 1, (
        f"Expected 1 alert within the 2 minute timerange, got {len(results)}. "
        "A sub-day timerange was truncated to zero days and the filter dropped."
    )
    assert results[0].id == "recent-alert-timerange"


def test_calculate_time_delta_keeps_sub_day_precision():
    """_calculate_time_delta must not round a sub-day window down to zero."""
    provider = KeepProvider.__new__(KeepProvider)

    two_minutes = provider._calculate_time_delta(
        timerange={
            "from": "2026-09-21T23:00:00Z",
            "to": "2026-09-21T23:02:00Z",
        }
    )
    assert two_minutes == pytest.approx(120 / 86400)

    one_hour = provider._calculate_time_delta(
        timerange={
            "from": "2026-09-21T22:00:00Z",
            "to": "2026-09-21T23:00:00Z",
        }
    )
    assert one_hour == pytest.approx(1 / 24)


def test_parse_provider_parameters_keeps_float():
    """
    A float step parameter must survive parsing.

    parse_provider_parameters only copied str/list/int/bool (and dict) through,
    so a float was dropped with no error and the provider fell back to its
    default. That is what made `time_delta: 0.1667` behave as one full day.
    """
    from keep.parser.parser import Parser

    parsed = Parser.parse_provider_parameters(
        {
            "time_delta": 0.001388888888888889,
            "limit": 10,
            "filter": "status == 'firing'",
            "distinct": True,
        }
    )

    assert "time_delta" in parsed, "float parameter was dropped during parsing"
    assert parsed["time_delta"] == pytest.approx(0.001388888888888889)
    assert parsed["limit"] == 10
    assert parsed["filter"] == "status == 'firing'"
    assert parsed["distinct"] is True
