import datetime
import json
import time
from datetime import timezone, timedelta

import pytest
from freezegun import freeze_time
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.alerts import query_last_alerts
from keep.api.core.db import cleanup_expired_dismissals, get_session
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.models.query import QueryDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine
from tests.fixtures.client import client, setup_api_key, test_app


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_time_travel_dismissal_expiration(
    db_session, test_app, create_alert, caplog
):
    """Test dismissal expiration by actually moving time forward using freezegun."""
    
    # Start at 10:00 AM
    start_time = datetime.datetime(2025, 6, 17, 10, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(start_time) as frozen_time:
        print(f"\n=== Starting at {frozen_time.time_to_freeze} ===")
        
        # Create an alert at 10:00 AM
        fingerprint = "time-travel-alert"
        create_alert(
            fingerprint,
            AlertStatus.FIRING,
            start_time,
            {
                "name": "Time Travel Test Alert",
                "severity": "critical",
                "service": "time-service",
            },
        )
        
        # Dismiss the alert until 10:30 AM (30 minutes later)
        dismiss_until_time = start_time + timedelta(minutes=30)
        dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        caplog.clear()
        
        enrichment_bl = EnrichmentsBl("keep", db=db_session)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint,
            enrichments={
                "dismissed": True,
                "dismissedUntil": dismiss_until_str,
                "note": "Dismissed for 30 minutes"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Time travel dismissal test"
        )
        
        # At 10:00 AM - alert should be dismissed
        print(f"\n=== Time: {frozen_time.time_to_freeze} (Alert dismissed until {dismiss_until_time}) ===")
        
        # Test CEL filter for dismissed == true (should find the alert)
        db_alerts, total_count = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint
        assert alerts_dto[0].dismissed is True
        print(f"✓ At 10:00 AM: Alert correctly appears in dismissed == true filter")
        
        # Test CEL filter for dismissed == false (should NOT find the alert)
        db_alerts, total_count = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 0
        print(f"✓ At 10:00 AM: Alert correctly does NOT appear in dismissed == false filter")
        
        # Travel to 10:15 AM - alert should still be dismissed
        frozen_time.tick(timedelta(minutes=15))
        print(f"\n=== Time: {frozen_time.time_to_freeze} (Still within dismissal period) ===")
        
        caplog.clear()
        
        # Test dismissed == true (should still find the alert)
        db_alerts, total_count = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 1
        assert alerts_dto[0].dismissed is True
        print(f"✓ At 10:15 AM: Alert still correctly dismissed")
        
        # Check that cleanup ran but found no expired dismissals
        assert "No expired dismissals found to clean up" in caplog.text
        print(f"✓ At 10:15 AM: Cleanup correctly identified no expired dismissals")
        
        # Travel to 10:45 AM - PAST the dismissal expiration time
        frozen_time.tick(timedelta(minutes=30))  # Now at 10:45 AM, dismissed until 10:30 AM
        print(f"\n=== Time: {frozen_time.time_to_freeze} (PAST dismissal expiration!) ===")
        
        caplog.clear()
        
        # Now test dismissed == false - the cleanup should run and find the alert
        db_alerts, total_count = query_last_alerts(
            tenant_id="keep", 
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        # This is the key test - after expiration, alert should appear in dismissed == false
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint
        assert alerts_dto[0].dismissed is False
        print(f"✅ At 10:45 AM: Alert correctly appears in dismissed == false filter after expiration!")
        
        # Verify cleanup logs show the dismissal was updated
        assert "Starting cleanup of expired dismissals" in caplog.text
        assert "Updating expired dismissal for alert" in caplog.text 
        assert "Successfully updated expired dismissal" in caplog.text
        print(f"✓ At 10:45 AM: Cleanup logs confirm dismissal was properly updated")
        
        # Test dismissed == true - should NOT find the expired alert
        db_alerts, total_count = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 0
        print(f"✓ At 10:45 AM: Alert correctly does NOT appear in dismissed == true filter after expiration")
        
        print(f"\n🎉 Time travel test completed successfully!")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_multiple_alerts_mixed_expiration_times(
    db_session, test_app, create_alert, caplog
):
    """Test multiple alerts with different expiration times using freezegun."""
    
    start_time = datetime.datetime(2025, 6, 17, 14, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(start_time) as frozen_time:
        # Create 3 alerts with different dismissal periods
        fingerprint1 = "alert-expires-in-10min"
        create_alert(
            fingerprint1,
            AlertStatus.FIRING,
            start_time,
            {"name": "Alert 1 - Expires in 10min", "severity": "critical"},
        )
        
        fingerprint2 = "alert-expires-in-30min"
        create_alert(
            fingerprint2,
            AlertStatus.FIRING,
            start_time,
            {"name": "Alert 2 - Expires in 30min", "severity": "warning"},
        )
        
        fingerprint3 = "alert-never-expires"
        create_alert(
            fingerprint3,
            AlertStatus.FIRING,
            start_time,
            {"name": "Alert 3 - Never expires", "severity": "info"},
        )
        
        enrichment_bl = EnrichmentsBl("keep", db=db_session)
        
        # Dismiss alert1 until 14:10 (10 minutes)
        dismiss_time_1 = start_time + timedelta(minutes=10)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint1,
            enrichments={
                "dismissed": True,
                "dismissedUntil": dismiss_time_1.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Dismissed for 10 minutes"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Short dismissal"
        )
        
        # Dismiss alert2 until 14:30 (30 minutes)
        dismiss_time_2 = start_time + timedelta(minutes=30)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint2,
            enrichments={
                "dismissed": True,
                "dismissedUntil": dismiss_time_2.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Dismissed for 30 minutes"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Medium dismissal"
        )
        
        # Dismiss alert3 forever
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint3,
            enrichments={
                "dismissed": True,
                "dismissedUntil": "forever",
                "note": "Dismissed forever"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Forever dismissal"
        )
        
        print(f"\n=== Time: {frozen_time.time_to_freeze} - All alerts dismissed ===")
        
        # At 14:00 - all alerts should be dismissed
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 3
        print(f"✓ All 3 alerts correctly dismissed initially")
        
        # No alerts should be in not-dismissed
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 0
        print(f"✓ No alerts in non-dismissed filter initially")
        
        # Travel to 14:15 - alert1 should have expired, others still dismissed
        frozen_time.tick(timedelta(minutes=15))
        print(f"\n=== Time: {frozen_time.time_to_freeze} - Alert1 should have expired ===")
        
        caplog.clear()
        
        # Check dismissed == false - should find alert1 only
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint1
        print(f"✓ Alert1 correctly expired and appears in non-dismissed filter")
        
        # Check dismissed == true - should find alert2 and alert3
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 2
        dismissed_fingerprints = {alert.fingerprint for alert in alerts_dto}
        assert fingerprint2 in dismissed_fingerprints
        assert fingerprint3 in dismissed_fingerprints
        print(f"✓ Alert2 and Alert3 still correctly dismissed")
        
        # Travel to 14:45 - alert2 should also have expired, alert3 still dismissed
        frozen_time.tick(timedelta(minutes=30))
        print(f"\n=== Time: {frozen_time.time_to_freeze} - Alert2 should now also have expired ===")
        
        caplog.clear()
        
        # Check dismissed == false - should find alert1 and alert2
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 2
        not_dismissed_fingerprints = {alert.fingerprint for alert in alerts_dto}
        assert fingerprint1 in not_dismissed_fingerprints
        assert fingerprint2 in not_dismissed_fingerprints
        print(f"✓ Alert1 and Alert2 both correctly expired and appear in non-dismissed filter")
        
        # Check dismissed == true - should find only alert3 (forever dismissal)
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint3
        print(f"✓ Alert3 still correctly dismissed forever")
        
        # Verify cleanup logs
        assert "Starting cleanup of expired dismissals" in caplog.text
        assert "Successfully updated expired dismissal" in caplog.text
        print(f"✓ Cleanup logs confirm expired dismissals were updated")
        
        print(f"\n🎉 Mixed expiration times test completed successfully!")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_api_endpoint_time_travel_scenario(
    db_session, client, test_app, create_alert, caplog
):
    """Test API endpoints with actual time travel using freezegun."""
    
    start_time = datetime.datetime(2025, 6, 17, 16, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(start_time) as frozen_time:
        # Create an alert at 16:00
        fingerprint = "api-time-travel-alert"
        create_alert(
            fingerprint,
            AlertStatus.FIRING,
            start_time,
            {
                "name": "API Time Travel Alert",
                "severity": "high",
            },
        )
        
        # Dismiss until 16:20 (20 minutes later) via API
        dismiss_until_time = start_time + timedelta(minutes=20)
        dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        response = client.post(
            "/alerts/batch_enrich",
            headers={"x-api-key": "some-key"},
            json={
                "fingerprints": [fingerprint],
                "enrichments": {
                    "dismissed": "true",
                    "dismissedUntil": dismiss_until_str,
                    "note": "API dismissal test"
                },
            },
        )
        assert response.status_code == 200
        
        time.sleep(1)  # Allow processing
        
        print(f"\n=== Time: {frozen_time.time_to_freeze} (Alert dismissed via API until {dismiss_until_time}) ===")
        
        # At 16:00 - alert should be dismissed
        response = client.post(
            "/alerts/query",
            headers={"x-api-key": "some-key"},
            json={
                "cel": "dismissed == true",
                "limit": 100
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["count"] == 1
        assert result["results"][0]["fingerprint"] == fingerprint
        print(f"✓ API confirms alert is dismissed at 16:00")
        
        # Travel to 16:30 - PAST the dismissal time
        frozen_time.tick(timedelta(minutes=30))
        print(f"\n=== Time: {frozen_time.time_to_freeze} (PAST dismissal expiration via API) ===")
        
        caplog.clear()
        
        # Query for non-dismissed alerts - should find our alert
        response = client.post(
            "/alerts/query",
            headers={"x-api-key": "some-key"},
            json={
                "cel": "dismissed == false",
                "limit": 100
            },
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Key test: expired dismissal should appear in non-dismissed results
        assert result["count"] == 1
        found_alert = result["results"][0]
        assert found_alert["fingerprint"] == fingerprint
        assert found_alert["dismissed"] is False
        print(f"✅ API correctly returns expired alert in dismissed == false filter!")
        
        # Verify cleanup happened
        assert "Starting cleanup of expired dismissals" in caplog.text
        print(f"✓ API endpoint triggered cleanup as expected")
        
        print(f"\n🎉 API time travel test completed successfully!")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_cleanup_function_direct_time_scenarios(
    db_session, test_app, create_alert, caplog
):
    """Test the cleanup function directly with various time scenarios."""
    
    base_time = datetime.datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(base_time) as frozen_time:
        # Create alerts
        fingerprint1 = "cleanup-test-1"
        fingerprint2 = "cleanup-test-2"
        fingerprint3 = "cleanup-test-3"
        
        create_alert(fingerprint1, AlertStatus.FIRING, base_time, {"name": "Cleanup Test 1"})
        create_alert(fingerprint2, AlertStatus.FIRING, base_time, {"name": "Cleanup Test 2"})
        create_alert(fingerprint3, AlertStatus.FIRING, base_time, {"name": "Cleanup Test 3"})
        
        enrichment_bl = EnrichmentsBl("keep", db=db_session)
        
        # Set up dismissals with different scenarios
        # Alert1: Expired 1 hour ago
        past_time = base_time - timedelta(hours=1)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint1,
            enrichments={
                "dismissed": True,
                "dismissedUntil": past_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Already expired"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Pre-expired dismissal"
        )
        
        # Alert2: Expires in 1 hour
        future_time = base_time + timedelta(hours=1)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint2,
            enrichments={
                "dismissed": True,
                "dismissedUntil": future_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Future expiration"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Future dismissal"
        )
        
        # Alert3: Forever dismissal
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint3,
            enrichments={
                "dismissed": True,
                "dismissedUntil": "forever",
                "note": "Never expires"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Forever dismissal"
        )
        
        print(f"\n=== Testing cleanup function directly at {frozen_time.time_to_freeze} ===")
        
        caplog.clear()
        
        # Run cleanup - should only update alert1 (already expired)
        cleanup_expired_dismissals("keep", db_session)
        
        # Verify logs
        assert "Starting cleanup of expired dismissals" in caplog.text
        assert "Found 3 potentially expired dismissals to check" in caplog.text
        assert "Updating expired dismissal for alert" in caplog.text
        assert "Successfully updated expired dismissal" in caplog.text
        assert "Cleanup completed successfully" in caplog.text
        print(f"✓ Cleanup function processed all dismissals correctly")
        
        # Test the state after cleanup
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        # Should find alert1 (was already expired)
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint1
        print(f"✓ Alert1 correctly cleaned up (was already expired)")
        
        # Move forward 2 hours - now alert2 should also expire
        frozen_time.tick(timedelta(hours=2))
        print(f"\n=== After moving 2 hours forward to {frozen_time.time_to_freeze} ===")
        
        caplog.clear()
        
        # Run cleanup again
        cleanup_expired_dismissals("keep", db_session)
        
        # Now should clean up alert2 as well
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        # Should find alert1 and alert2 (both expired)
        assert len(alerts_dto) == 2
        not_dismissed_fingerprints = {alert.fingerprint for alert in alerts_dto}
        assert fingerprint1 in not_dismissed_fingerprints
        assert fingerprint2 in not_dismissed_fingerprints
        print(f"✓ Alert2 also correctly cleaned up after time passed")
        
        # Alert3 should still be dismissed (forever)
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        assert len(alerts_dto) == 1
        assert alerts_dto[0].fingerprint == fingerprint3
        print(f"✓ Alert3 still correctly dismissed forever")
        
        print(f"\n🎉 Direct cleanup function test completed successfully!")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_edge_cases_with_time_travel(
    db_session, test_app, create_alert, caplog
):
    """Test edge cases using time travel."""
    
    base_time = datetime.datetime(2025, 6, 17, 9, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(base_time) as frozen_time:
        # Create alerts for edge case testing
        fingerprint_invalid = "invalid-time"
        fingerprint_exact = "exact-boundary"
        fingerprint_micro = "microseconds"
        
        create_alert(fingerprint_invalid, AlertStatus.FIRING, base_time, {"name": "Invalid Time"})
        create_alert(fingerprint_exact, AlertStatus.FIRING, base_time, {"name": "Exact Boundary"})
        create_alert(fingerprint_micro, AlertStatus.FIRING, base_time, {"name": "Microseconds Test"})
        
        enrichment_bl = EnrichmentsBl("keep", db=db_session)
        
        # Test 1: Alert with malformed dismissedUntil (should be skipped gracefully)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint_invalid,
            enrichments={
                "dismissed": True,
                "dismissedUntil": "not-a-valid-date",
                "note": "Invalid date format"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Invalid date test"
        )
        
        # Test 2: Alert dismissed until EXACTLY the current time
        exact_boundary_time = base_time
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint_exact,
            enrichments={
                "dismissed": True,
                "dismissedUntil": exact_boundary_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Exact boundary test"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Exact boundary dismissal"
        )
        
        # Test 3: Alert with microsecond precision dismissal
        microsecond_time = base_time - timedelta(microseconds=1)
        enrichment_bl.enrich_entity(
            fingerprint=fingerprint_micro,
            enrichments={
                "dismissed": True,
                "dismissedUntil": microsecond_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "note": "Microsecond precision test"
            },
            action_type=ActionType.GENERIC_ENRICH,
            action_callee="test_user",
            action_description="Microsecond dismissal"
        )
        
        print(f"\n=== Running edge case tests at {frozen_time.time_to_freeze} ===")
        
        caplog.clear()
        
        # Run a CEL query to trigger cleanup
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        # Should find exactly boundary and microseconds alerts (both expired)
        not_dismissed_fingerprints = {alert.fingerprint for alert in alerts_dto}
        
        # Exact boundary should be included (current_time >= dismissed_until)
        assert fingerprint_exact in not_dismissed_fingerprints
        print(f"✓ Exact boundary dismissal correctly expired (>= comparison)")
        
        # Microsecond precision should be handled correctly
        assert fingerprint_micro in not_dismissed_fingerprints
        print(f"✓ Microsecond precision dismissal correctly expired")
        
        # Invalid date should still be dismissed (cleanup skips it)
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        
        dismissed_fingerprints = {alert.fingerprint for alert in alerts_dto}
        assert fingerprint_invalid in dismissed_fingerprints
        print(f"✓ Invalid date format alert remains dismissed (cleanup skipped it gracefully)")
        
        # Check logs for handling of invalid date
        assert "Failed to parse dismissedUntil" in caplog.text
        print(f"✓ Invalid date format logged correctly")
        
        print(f"\n🎉 Edge case tests completed successfully!")


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_performance_with_many_alerts_time_travel(
    db_session, test_app, create_alert, caplog
):
    """Test cleanup performance with many alerts using time travel."""
    
    base_time = datetime.datetime(2025, 6, 17, 18, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(base_time) as frozen_time:
        print(f"\n=== Creating 20 alerts for performance test ===")
        
        alerts = []
        enrichment_bl = EnrichmentsBl("keep", db=db_session)
        
        # Create 20 alerts with various dismissal times
        for i in range(20):
            fingerprint = f"perf-alert-{i}"
            create_alert(
                fingerprint,
                AlertStatus.FIRING,
                base_time,
                {"name": f"Performance Test Alert {i}", "severity": "warning"}
            )
            
            # Mix of dismissal scenarios
            if i < 5:
                # First 5: Expire in 10 minutes
                expire_time = base_time + timedelta(minutes=10)
            elif i < 10:
                # Next 5: Expire in 30 minutes
                expire_time = base_time + timedelta(minutes=30)
            elif i < 15:
                # Next 5: Already expired (1 hour ago)
                expire_time = base_time - timedelta(hours=1)
            else:
                # Last 5: Forever dismissal
                expire_time = None
            
            if expire_time:
                dismiss_until_str = expire_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                dismiss_until_str = "forever"
            
            enrichment_bl.enrich_entity(
                fingerprint=fingerprint,
                enrichments={
                    "dismissed": True,
                    "dismissedUntil": dismiss_until_str,
                    "note": f"Performance test dismissal {i}"
                },
                action_type=ActionType.GENERIC_ENRICH,
                action_callee="test_user",
                action_description=f"Perf test dismissal {i}"
            )
            
            alerts.append({"fingerprint": fingerprint, "expire_time": expire_time})
        
        print(f"✓ Created 20 alerts with mixed dismissal scenarios")
        
        # Initial state: 5 expired, 15 still dismissed
        caplog.clear()
        
        start_time = time.time()
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        cleanup_time = time.time() - start_time
        
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 5  # 5 already expired
        print(f"✓ Initial cleanup found 5 expired alerts in {cleanup_time:.3f}s")
        
        # Travel forward 15 minutes - 5 more should expire
        frozen_time.tick(timedelta(minutes=15))
        print(f"\n=== Time: {frozen_time.time_to_freeze} - 5 more alerts should expire ===")
        
        caplog.clear()
        start_time = time.time()
        
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        cleanup_time = time.time() - start_time
        
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 10  # 10 total expired now
        print(f"✓ After 15 minutes: found 10 expired alerts in {cleanup_time:.3f}s")
        
        # Travel forward another 20 minutes - 5 more should expire
        frozen_time.tick(timedelta(minutes=20))
        print(f"\n=== Time: {frozen_time.time_to_freeze} - All timed dismissals should be expired ===")
        
        caplog.clear()
        start_time = time.time()
        
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        cleanup_time = time.time() - start_time
        
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 15  # 15 total expired (5 are forever)
        print(f"✓ After 35 minutes: found 15 expired alerts in {cleanup_time:.3f}s")
        
        # Check that forever dismissals are still dismissed
        db_alerts, _ = query_last_alerts(
            tenant_id="keep",
            query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
        )
        alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
        assert len(alerts_dto) == 5  # 5 forever dismissals
        print(f"✓ 5 forever dismissals still correctly dismissed")
        
        # Verify cleanup ran efficiently
        assert "Starting cleanup of expired dismissals" in caplog.text
        assert "Cleanup completed successfully" in caplog.text
        print(f"✓ Cleanup completed successfully for 20 alerts")
        
        print(f"\n🎉 Performance test with 20 alerts completed successfully!")


if __name__ == "__main__":
    # Run the tests individually for debugging
    pass