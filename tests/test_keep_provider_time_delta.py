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