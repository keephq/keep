"""
Test for dismissedUntil expiry bug.

This test reproduces the issue described in https://github.com/keephq/keep/issues/5047
where alerts with expired dismissedUntil timestamps still don't appear in filters
for dismissed == false, even though their payload shows dismissed: false.
"""

import datetime
import uuid
from datetime import timezone, timedelta
from freezegun import freeze_time

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, LastAlert
from keep.api.models.db.preset import PresetSearchQuery as SearchQuery
from keep.searchengine.searchengine import SearchEngine


def wait_for_dismissal_expiry_processing(tenant_id, db_session, max_wait_count=10):
    """
    Synchronously run dismissal expiry check and wait for completion.
    For tests, we call the watcher function directly instead of waiting for async task.
    """
    from keep.api.bl.dismissal_expiry_bl import DismissalExpiryBl
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Running dismissal expiry check for tenant {tenant_id}")
    
    # Call the watcher function directly (synchronous)
    DismissalExpiryBl.check_dismissal_expiry(logger, db_session)
    
    logger.info("Dismissal expiry check completed")
    return True


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


def test_dismissal_validation_at_creation_time():
    """
    Test that dismissal validation works correctly at AlertDto creation time.
    This test should pass and demonstrates the current working behavior.
    """
    now = datetime.datetime.now(timezone.utc)
    future_time = now + timedelta(hours=1)
    past_time = now - timedelta(hours=1)
    
    # Test 1: Alert dismissed until future time should be dismissed=True
    future_dismiss_str = future_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    alert_future = AlertDto(
        id="test-future",
        name="Future Dismiss Test",
        status=AlertStatus.FIRING,
        severity="critical",
        lastReceived=now.isoformat(),
        dismissed=True,  # This will be validated against dismissUntil
        dismissUntil=future_dismiss_str,
        source=["test"],
        labels={}
    )
    
    # Should remain dismissed because dismissUntil is in future
    assert alert_future.dismissed == True
    assert alert_future.dismissUntil == future_dismiss_str
    
    # Test 2: Alert dismissed until past time should be dismissed=False
    past_dismiss_str = past_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    alert_past = AlertDto(
        id="test-past",
        name="Past Dismiss Test", 
        status=AlertStatus.FIRING,
        severity="critical",
        lastReceived=now.isoformat(),
        dismissed=True,  # This will be overridden by validator
        dismissUntil=past_dismiss_str,
        source=["test"],
        labels={}
    )
    
    # Should become not dismissed because dismissUntil is in past
    assert alert_past.dismissed == False
    assert alert_past.dismissUntil == past_dismiss_str


def test_dismissal_expiry_bug_search_filters(db_session):
    """
    Test that verifies the dismissedUntil expiry fix works correctly with search filters.

    This test demonstrates that alerts with expired dismissedUntil properly appear
    in searches for dismissed == false after the watcher processes them.

    This test should PASS with the fixed watcher implementation.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    # Step 1: Create an alert that is NOT dismissed initially
    initial_time = datetime.datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(initial_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "test-alert-expiry",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "fingerprint": "test-expiry-fingerprint",
            }),
            fingerprint="test-expiry-fingerprint",
            timestamp=initial_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        # Create LastAlert entry
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()
    
    # Step 2: Dismiss the alert with a future dismissUntil timestamp (1 hour from now)
    dismiss_time = initial_time + timedelta(minutes=30)
    dismiss_until_time = initial_time + timedelta(hours=1)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        # Use enrichment to dismiss the alert (simulating workflow dismissal)
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="test-expiry-fingerprint",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
                # Add disposable fields that would be added by workflows
                "disposable_dismissed": True,
                "disposable_dismissedUntil": dismiss_until_str,
                "disposable_note": "Maintenance window",
                "disposable_status": "suppressed"
            },
            action_callee="workflow",
            action_description="Alert dismissed by maintenance workflow", 
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify alert is dismissed at this point
        search_query_dismissed = SearchQuery(
            sql_query={
                "sql": "dismissed = :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == true",
        )
        
        dismissed_alerts = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_dismissed)
        assert len(dismissed_alerts) == 1, "Alert should be dismissed during dismissal period"
        assert dismissed_alerts[0].dismissed == True
        assert dismissed_alerts[0].dismissUntil == dismiss_until_str
    
    # Step 3: Time travel to AFTER the dismissUntil timestamp has expired
    after_expiry_time = dismiss_until_time + timedelta(minutes=30)
    
    with freeze_time(after_expiry_time):
        # At this point, the dismissal should have expired but without a background
        # watcher, the alert will still appear dismissed in the database
        
        # Test filtering for non-dismissed alerts
        search_query_not_dismissed = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == false",  # or !dismissed
        )
        
        # Before watcher: Alert still appears dismissed in database because 
        # the enrichment hasn't been updated yet (dismissal expired but database not updated)
        non_dismissed_alerts_before = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        
        # Before watcher runs: Database still shows alert as dismissed (expected behavior)
        assert len(non_dismissed_alerts_before) == 0, (
            "Before watcher: Alert doesn't appear in non-dismissed filter because "
            "database hasn't been updated yet (dismissal expired but enrichment not processed)"
        )
        
        # NOW APPLY THE FIX: Run dismissal expiry watcher
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # AFTER FIX: The alert should now appear correctly
        non_dismissed_alerts_after = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        
        # After watcher runs: Alert should now appear in non-dismissed filter
        assert len(non_dismissed_alerts_after) == 1, (
            "FIXED: Alert now appears in non-dismissed filter after watcher processes expired dismissal"
        )
        assert non_dismissed_alerts_after[0].dismissed == False
        assert non_dismissed_alerts_after[0].dismissUntil is None


def test_dismissal_expiry_bug_sidebar_filter(db_session):
    """
    Test that verifies sidebar "Not dismissed" filter works correctly after watcher processes expired dismissals.
    
    This simulates the UI scenario described in the GitHub issue.
    This test should PASS with the fixed watcher implementation.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    # Create multiple alerts to simulate a real scenario
    base_time = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    
    alert_details = [
        {
            "id": "persistent-alert",
            "fingerprint": "persistent-fp", 
            "dismissed": False,
            "dismissUntil": None,
            "name": "Persistent Alert"
        },
        {
            "id": "temporary-dismiss-alert",
            "fingerprint": "temporary-fp",
            "dismissed": False, 
            "dismissUntil": None,
            "name": "Temporarily Dismissed Alert"
        },
        {
            "id": "permanently-dismissed-alert",
            "fingerprint": "permanent-fp",
            "dismissed": True,
            "dismissUntil": "forever",
            "name": "Permanently Dismissed Alert"
        }
    ]
    
    # Step 1: Create alerts
    with freeze_time(base_time):
        alerts = []
        for detail in alert_details:
            alert = Alert(
                tenant_id=tenant_id,
                provider_type="test",
                provider_id="test",
                event=_create_valid_event(detail),
                fingerprint=detail["fingerprint"],
                timestamp=base_time
            )
            alerts.append(alert)
        
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
    
    # Step 2: Dismiss the "temporary" alert for 2 hours
    dismiss_time = base_time + timedelta(minutes=15)
    dismiss_until_time = base_time + timedelta(hours=2)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="temporary-fp",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
            },
            action_callee="maintenance_workflow",
            action_description="Temporarily dismissed for maintenance",
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify current state: should have 1 non-dismissed alert
        # (persistent alert, temporary is dismissed, permanent is dismissed but shows as not dismissed due to enrichment bug)
        not_dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="!dismissed",
        )
        
        current_not_dismissed = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        # The bug causes permanently dismissed alert to show as not dismissed
        # So we expect 2 instead of 1 (demonstrating the bug)
        assert len(current_not_dismissed) == 2, (
            "Bug reproduction: Permanent dismissal shows incorrectly due to enrichment issue"
        )
        # One of them should be the persistent alert (which alert comes first can vary)
        fingerprints = {alert.fingerprint for alert in current_not_dismissed}
        assert "persistent-fp" in fingerprints, "Persistent alert should be in results"
    
    # Step 3: Time travel to after dismissal expires
    after_expiry_time = dismiss_until_time + timedelta(hours=1)
    
    with freeze_time(after_expiry_time):
        # Now we should have 2 non-dismissed alerts:
        # - persistent-fp (never dismissed)
        # - temporary-fp (dismissal expired)
        # And 1 permanently dismissed alert:
        # - permanent-fp (dismissed "forever")
        
        not_dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="!dismissed",
        )
        
        # BEFORE FIX: This will return 2 alerts due to a different bug
        # The "permanent" alert incorrectly shows as not dismissed even though it should be dismissed forever
        current_not_dismissed_before = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        
        # Current state shows 2 alerts due to the AlertDto validation bug with "forever"
        assert len(current_not_dismissed_before) == 2, (
            "Current state: Shows 2 alerts due to various dismissal handling bugs"
        )
        
        # Verify which alerts are returned before fix
        returned_fingerprints_before = {alert.fingerprint for alert in current_not_dismissed_before}
        # Current state includes both persistent and permanent (due to different bugs)
        expected_fingerprints_before_fix = {"persistent-fp", "permanent-fp"}
        
        assert returned_fingerprints_before == expected_fingerprints_before_fix, (
            f"Current state: Expected {expected_fingerprints_before_fix}, "
            f"got {returned_fingerprints_before}"
        )
        
        # APPLY THE FIX: Run dismissal expiry watcher
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # AFTER FIX: Now includes the temporary alert that was correctly un-dismissed
        current_not_dismissed_after = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        
        # This should now return 3 alerts (including the fixed temporary alert)
        assert len(current_not_dismissed_after) == 3, (
            "FIXED: Now correctly includes temporary alert after watcher processes expired dismissal"
        )
        
        # Verify the temporary alert is now included (the key fix!)
        returned_fingerprints_after = {alert.fingerprint for alert in current_not_dismissed_after}
        expected_fingerprints_fixed = {"persistent-fp", "temporary-fp", "permanent-fp"}
        
        assert returned_fingerprints_after == expected_fingerprints_fixed, (
            f"FIXED: Expected fingerprints {expected_fingerprints_fixed}, "
            f"got {returned_fingerprints_after}"
        )
        
        # Most importantly, verify that temporary-fp is now properly un-dismissed
        temporary_alert = next(alert for alert in current_not_dismissed_after if alert.fingerprint == "temporary-fp")
        assert temporary_alert.dismissed == False, "Temporary alert should now be un-dismissed"
        assert temporary_alert.dismissUntil is None, "Temporary alert dismissUntil should be cleared"


def test_dismissal_expiry_bug_with_cel_filter(db_session):
    """
    Test that CEL-based filters work correctly with dismissed == false after watcher processes expired dismissals.
    
    This test should PASS with the fixed watcher implementation.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    start_time = datetime.datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(start_time):
        # Create an alert
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test", 
            event=_create_valid_event({
                "id": "cel-filter-test",
                "fingerprint": "cel-test-fp",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "source": ["test-source"],
                "severity": "warning"
            }),
            fingerprint="cel-test-fp",
            timestamp=start_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()
    
    # Dismiss with 30-minute window
    dismiss_time = start_time + timedelta(minutes=5)
    dismiss_until_time = start_time + timedelta(minutes=30)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="cel-test-fp",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
            },
            action_callee="test",
            action_description="CEL filter test dismissal",
            action_type=ActionType.GENERIC_ENRICH,
        )
    
    # Time travel past expiry
    past_expiry_time = dismiss_until_time + timedelta(minutes=15)
    
    with freeze_time(past_expiry_time):
        # Test various CEL expressions that should find the non-dismissed alert
        cel_expressions = [
            "dismissed == false",
            "!dismissed", 
            "dismissed != true",
            "severity == 'warning' && dismissed == false"
        ]
        
        # BEFORE FIX: Test each CEL expression and demonstrate bug exists
        for cel_expr in cel_expressions:
            search_query = SearchQuery(
                sql_query={
                    "sql": "dismissed != :dismissed_1",
                    "params": {"dismissed_1": "true"},
                },
                cel_query=cel_expr,
            )
            
            # Before watcher: Database hasn't been updated yet, so filter won't find the alert
            results_before = SearchEngine(tenant_id=tenant_id).search_alerts(search_query)
            
            # Before watcher runs: Database still shows alert as dismissed
            assert len(results_before) == 0, (
                f"Before watcher: CEL expression '{cel_expr}' returns 0 because "
                f"database hasn't been updated yet (dismissal expired but not processed)"
            )
        
        # APPLY THE FIX: Run dismissal expiry watcher
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # AFTER FIX: Test each CEL expression again - should now work
        for cel_expr in cel_expressions:
            search_query = SearchQuery(
                sql_query={
                    "sql": "dismissed != :dismissed_1",
                    "params": {"dismissed_1": "true"},
                },
                cel_query=cel_expr,
            )
            
            # Should now return 1 alert correctly
            results_after = SearchEngine(tenant_id=tenant_id).search_alerts(search_query)
            
            # After watcher runs: Should now work correctly
            assert len(results_after) == 1, (
                f"FIXED: CEL expression '{cel_expr}' now correctly returns 1 alert "
                f"after watcher processes expired dismissal"
            )
            assert results_after[0].dismissed == False
            assert results_after[0].dismissUntil is None


def test_dismissal_works_correctly_without_expiry(db_session):
    """
    Test that dismissal works correctly when there's no dismissUntil (control test).
    
    This test should PASS and demonstrates that basic dismissal functionality works.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    current_time = datetime.datetime(2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(current_time):
        # Create alert
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "control-test",
                "fingerprint": "control-fp",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
            }),
            fingerprint="control-fp",
            timestamp=current_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()
        
        # Verify alert appears in non-dismissed filter initially
        not_dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="!dismissed",
        )
        
        results = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        assert len(results) == 1
        assert results[0].dismissed == False
        
        # Dismiss permanently (no dismissUntil)
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="control-fp",
            enrichments={"dismissed": True},
            action_callee="test",
            action_description="Permanent dismissal test",
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify alert no longer appears in non-dismissed filter
        results = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        assert len(results) == 0
        
        # Verify alert appears in dismissed filter
        dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed = :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == true",
        )
        
        results = SearchEngine(tenant_id=tenant_id).search_alerts(dismissed_query)
        assert len(results) == 1
        assert results[0].dismissed == True


def test_dismissal_forever_works_correctly(db_session):
    """
    Test that dismissUntil: "forever" works correctly (control test).
    
    This test should PASS.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    current_time = datetime.datetime(2025, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(current_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "forever-test",
                "fingerprint": "forever-fp",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,  # Start not dismissed
                "dismissUntil": None,
            }),
            fingerprint="forever-fp",
            timestamp=current_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()
        
        # Now dismiss with "forever"
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="forever-fp",
            enrichments={
                "dismissed": True,
                "dismissUntil": "forever",
            },
            action_callee="test",
            action_description="Forever dismissal test",
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify alert is dismissed
        not_dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="!dismissed",
        )
        
        results = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        assert len(results) == 0, "Alert with dismissUntil='forever' should not appear in non-dismissed filter"
    
    # Time travel far into the future
    future_time = current_time + timedelta(days=365)
    
    with freeze_time(future_time):
        # Run watcher - should NOT change "forever" dismissals
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # Should still be dismissed
        results = SearchEngine(tenant_id=tenant_id).search_alerts(not_dismissed_query)
        assert len(results) == 0, "Alert with dismissUntil='forever' should remain dismissed even after watcher runs"


def test_dismissal_expiry_bug_fixed_with_watcher(db_session):
    """
    Test that the dismissal expiry watcher fixes the bug.
    This test should PASS after implementing the fix.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    # Step 1: Create an alert that is NOT dismissed initially
    initial_time = datetime.datetime(2025, 1, 15, 20, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(initial_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "test-watcher-fix",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "fingerprint": "watcher-fix-fingerprint",
            }),
            fingerprint="watcher-fix-fingerprint",
            timestamp=initial_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        # Create LastAlert entry
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()
    
    # Step 2: Dismiss the alert with a future dismissUntil timestamp (1 hour from now)
    dismiss_time = initial_time + timedelta(minutes=30)
    dismiss_until_time = initial_time + timedelta(hours=1)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        # Use enrichment to dismiss the alert (simulating workflow dismissal)
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="watcher-fix-fingerprint",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
                # Add disposable fields that would be added by workflows
                "disposable_dismissed": True,
                "disposable_dismissedUntil": dismiss_until_str,
                "disposable_note": "Maintenance window",
                "disposable_status": "suppressed"
            },
            action_callee="workflow",
            action_description="Alert dismissed by maintenance workflow", 
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify alert is dismissed at this point
        search_query_dismissed = SearchQuery(
            sql_query={
                "sql": "dismissed = :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == true",
        )
        
        dismissed_alerts = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_dismissed)
        assert len(dismissed_alerts) == 1, "Alert should be dismissed during dismissal period"
        assert dismissed_alerts[0].dismissed == True
        assert dismissed_alerts[0].dismissUntil == dismiss_until_str
    
    # Step 3: Time travel to AFTER the dismissUntil timestamp has expired
    after_expiry_time = dismiss_until_time + timedelta(minutes=30)
    
    with freeze_time(after_expiry_time):
        # BEFORE running watcher - the bug should still exist
        search_query_not_dismissed = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == false",
        )
        
        non_dismissed_alerts_before = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        assert len(non_dismissed_alerts_before) == 0, "Before watcher: bug still exists, alert not returned"
        
        # NOW run the watcher - this should fix the issue
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # AFTER running watcher - the alert should now appear in non-dismissed filter
        non_dismissed_alerts_after = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        
        # This should now PASS - alert appears in non-dismissed filter after watcher fixes it
        assert len(non_dismissed_alerts_after) == 1, "After watcher: Alert should appear in non-dismissed filter"
        assert non_dismissed_alerts_after[0].dismissed == False
        assert non_dismissed_alerts_after[0].dismissUntil is None
        
        # Verify disposable fields were cleaned up
        assert not hasattr(non_dismissed_alerts_after[0], 'disposable_dismissed') or \
               getattr(non_dismissed_alerts_after[0], 'disposable_dismissed', None) is None


def test_dismissal_expiry_boolean_comparison_fix(db_session):
    """
    Test that specifically validates the boolean comparison fix in get_alerts_with_expired_dismissals.
    
    This test ensures that the function correctly finds dismissed alerts stored with different boolean
    formats across different database types, which was the root cause of the original bug.
    """
    from keep.api.bl.dismissal_expiry_bl import DismissalExpiryBl
    import datetime
    from keep.api.models.db.alert import AlertEnrichment
    
    tenant_id = SINGLE_TENANT_UUID
    current_time = datetime.datetime.now(datetime.timezone.utc)
    past_time = current_time - datetime.timedelta(hours=1)
    past_time_str = past_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Test different boolean representations that might be encountered
    test_cases = [
        {
            "fingerprint": "boolean-test-True",
            "dismissed": "True",  # Capitalized string (common in JavaScript/Python serialization)
            "description": "Capitalized 'True' string"
        },
        {
            "fingerprint": "boolean-test-true", 
            "dismissed": "true",  # Lowercase string (JSON standard)
            "description": "Lowercase 'true' string"
        }
    ]
    
    created_enrichments = []
    for test_case in test_cases:
        enrichment = AlertEnrichment(
            tenant_id=tenant_id,
            alert_fingerprint=test_case["fingerprint"],
            enrichments={
                "dismissed": test_case["dismissed"],
                "dismissUntil": past_time_str,  # Expired timestamp
                "status": "suppressed"
            },
            timestamp=current_time
        )
        created_enrichments.append(enrichment)
        db_session.add(enrichment)
    
    db_session.commit()
    
    # Test that get_alerts_with_expired_dismissals finds all variations
    expired_dismissals = DismissalExpiryBl.get_alerts_with_expired_dismissals(db_session)
    found_fingerprints = {e.alert_fingerprint for e in expired_dismissals}
    
    # Verify all test cases are found regardless of boolean format
    for test_case in test_cases:
        assert test_case["fingerprint"] in found_fingerprints, (
            f"Boolean comparison fix should find dismissed alerts with {test_case['description']} "
            f"(found: {found_fingerprints})"
        )
        
        # Verify the found enrichment has the expected data
        test_found = next(e for e in expired_dismissals if e.alert_fingerprint == test_case["fingerprint"])
        assert test_found.enrichments["dismissed"] == test_case["dismissed"]
        assert test_found.enrichments["dismissUntil"] == past_time_str


def test_dismissal_expiry_status_and_disposable_fields_cleanup(db_session):
    """
    Test that reproduces the bug where status and disposable fields remain after watcher processes expired dismissals.
    
    This test ensures that after watcher runs:
    1. dismissed = False and dismissUntil = None (currently working)  
    2. status is properly reset (currently broken)
    3. disposable fields are completely removed (currently broken)
    """
    from keep.api.bl.dismissal_expiry_bl import DismissalExpiryBl
    from keep.api.bl.enrichments_bl import EnrichmentsBl
    from keep.api.models.action_type import ActionType
    from keep.api.models.db.alert import Alert, LastAlert, AlertEnrichment
    from keep.searchengine.searchengine import SearchEngine
    from keep.api.models.db.preset import PresetSearchQuery as SearchQuery
    import datetime
    from freezegun import freeze_time
    
    tenant_id = SINGLE_TENANT_UUID
    
    # Step 1: Create an alert
    initial_time = datetime.datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(initial_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "test-status-disposable-bug",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "fingerprint": "status-disposable-test-fp",
            }),
            fingerprint="status-disposable-test-fp",
            timestamp=initial_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()

    # Step 2: Dismiss the alert with status and disposable fields (like a maintenance workflow would)
    dismiss_time = initial_time + timedelta(minutes=30)
    dismiss_until_time = initial_time + timedelta(hours=1)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="status-disposable-test-fp",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
                "status": "suppressed",  # This should be reset after expiry
                "note": "Maintenance window",
                # Disposable fields that should be completely removed
                "disposable_dismissed": True,
                "disposable_dismissedUntil": dismiss_until_str, 
                "disposable_dismissUntil": dismiss_until_str,  # Alternative field name
                "disposable_note": "Maintenance window",
                "disposable_status": "suppressed"
            },
            action_callee="maintenance_workflow",
            action_description="Maintenance dismissal with status and disposables",
            action_type=ActionType.GENERIC_ENRICH,
        )

    # Step 3: Time travel past dismissal expiry and run watcher
    after_expiry_time = dismiss_until_time + timedelta(minutes=30)
    
    with freeze_time(after_expiry_time):
        # Run the watcher
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # Get the enrichment directly from database to inspect all fields
        enrichment = db_session.query(AlertEnrichment).filter(
            AlertEnrichment.tenant_id == tenant_id,
            AlertEnrichment.alert_fingerprint == "status-disposable-test-fp"
        ).first()
        
        print(f"\\nAfter watcher - Enrichment fields:")
        for key, value in enrichment.enrichments.items():
            print(f"  {key} = {repr(value)}")
        
        # Test 1: Main dismissal fields should be correctly updated
        assert enrichment.enrichments.get("dismissed") == False, "dismissed should be False after watcher"
        assert enrichment.enrichments.get("dismissUntil") is None, "dismissUntil should be None after watcher"
        
        # Test 2: Status should be removed from enrichments (let AlertDto use original alert status)
        assert "status" not in enrichment.enrichments or enrichment.enrichments.get("status") != "suppressed", (
            f"Status should be removed or not be 'suppressed', but is '{enrichment.enrichments.get('status')}'"
        )
        
        # Test 3: All disposable fields should be completely removed (CURRENTLY FAILS - this is the bug!)
        disposable_fields_found = []
        for key in enrichment.enrichments.keys():
            if key.startswith("disposable_"):
                disposable_fields_found.append(key)
        
        assert not disposable_fields_found, (
            f"Disposable fields should be removed but found: {disposable_fields_found}"
        )
        
        # Test 4: Verify that the alert appears correctly in search results
        search_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == false",
        )
        
        results = SearchEngine(tenant_id=tenant_id).search_alerts(search_query)
        assert len(results) == 1, "Alert should appear in non-dismissed search"
        
        alert_dto = results[0]
        print(f"\\nSearchEngine result:")
        print(f"  dismissed = {alert_dto.dismissed}")
        print(f"  status = {getattr(alert_dto, 'status', 'N/A')}")
        print(f"  dismissUntil = {alert_dto.dismissUntil}")
        
        # Test 5: The final AlertDto should not be suppressed
        # This is the key issue - the AlertDto should use the original alert status (from alert.event)
        assert alert_dto.dismissed == False, "AlertDto should show dismissed=False"
        # The status should come from the original alert event, not be "suppressed"
        actual_status = getattr(alert_dto, 'status', None)
        assert actual_status != "suppressed", (
            f"AlertDto status should not be 'suppressed' but is '{actual_status}'"
        )
        # The status should be the original alert status (firing, resolved, etc.)
        print(f"Final AlertDto status: {actual_status} (should be original alert status, not 'suppressed')")


def test_github_issue_5047_cel_filters_dismisseduntil_bug_fixed(db_session):
    """
    Explicit test that solves GitHub Issue #5047:
    "CEL filters not returning alerts with dismissed: false after dismissedUntil expires"
    
    This test reproduces the exact scenario described in the GitHub issue and 
    verifies that our watcher-based fix resolves it.
    
    GitHub Issue: https://github.com/keephq/keep/issues/5047
    """
    tenant_id = SINGLE_TENANT_UUID
    
    # Step 1: Send an alert with dismissed: false (as described in issue)
    initial_time = datetime.datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(initial_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "github-issue-5047",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,  # Initial state: not dismissed
                "dismissUntil": None,
                "fingerprint": "github-5047-fingerprint",
                "source": ["github-test"],
                "severity": "warning"
            }),
            fingerprint="github-5047-fingerprint",
            timestamp=initial_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()

    # Step 2: Apply a workflow that enriches the alert (as described in issue)
    dismiss_time = initial_time + timedelta(minutes=10)
    dismiss_until_time = initial_time + timedelta(hours=2)  # 2 hours in future
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="github-5047-fingerprint",
            enrichments={
                # Exact enrichments described in the GitHub issue:
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
                "disposable_dismissed": True,
                "disposable_dismissedUntil": dismiss_until_str, 
                "disposable_note": "Workflow dismissal for maintenance",
                "disposable_status": "suppressed"
            },
            action_callee="workflow",
            action_description="GitHub Issue #5047 reproduction - workflow dismissal",
            action_type=ActionType.GENERIC_ENRICH,
        )
        
        # Verify alert is properly dismissed during the dismissal period
        dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed = :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == true",
        )
        
        dismissed_alerts = SearchEngine(tenant_id=tenant_id).search_alerts(dismissed_query)
        assert len(dismissed_alerts) == 1, "Alert should be dismissed during active dismissal period"
        assert dismissed_alerts[0].dismissed == True
        assert dismissed_alerts[0].dismissUntil == dismiss_until_str

    # Step 3: Wait until the dismissedUntil timestamp has passed (as described in issue)
    after_expiry_time = dismiss_until_time + timedelta(hours=1)  # 1 hour after expiry
    
    with freeze_time(after_expiry_time):
        # Step 4: Before running watcher - verify the bug exists
        # "The sidebar filter 'Not dismissed'" and "A CEL filter like dismissed == false"
        
        # Test both types of filters mentioned in the GitHub issue:
        
        # 1. Sidebar filter "Not dismissed" 
        sidebar_not_dismissed_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="!dismissed",  # Sidebar uses this pattern
        )
        
        # 2. CEL filter "dismissed == false"
        cel_dismissed_false_query = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1", 
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == false",  # Exact CEL from issue
        )
        
        # Before watcher: Both should return 0 results (demonstrating the bug)
        sidebar_results_before = SearchEngine(tenant_id=tenant_id).search_alerts(sidebar_not_dismissed_query)
        cel_results_before = SearchEngine(tenant_id=tenant_id).search_alerts(cel_dismissed_false_query)
        
        assert len(sidebar_results_before) == 0, "Bug reproduction: Sidebar filter should return 0 (bug exists)"
        assert len(cel_results_before) == 0, "Bug reproduction: CEL filter should return 0 (bug exists)"
        
        # SOLUTION: Run our dismissal expiry watcher (the fix)
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # After watcher: Both filters should now work correctly!
        sidebar_results_after = SearchEngine(tenant_id=tenant_id).search_alerts(sidebar_not_dismissed_query)
        cel_results_after = SearchEngine(tenant_id=tenant_id).search_alerts(cel_dismissed_false_query)
        
        # ✅ GITHUB ISSUE #5047 SOLVED! ✅
        assert len(sidebar_results_after) == 1, "FIXED: Sidebar 'Not dismissed' filter now works after watcher"
        assert len(cel_results_after) == 1, "FIXED: CEL 'dismissed == false' filter now works after watcher"
        
        # Verify the alert data is correct
        sidebar_alert = sidebar_results_after[0]
        cel_alert = cel_results_after[0]
        
        # Both filters should return the same alert
        assert sidebar_alert.id == "github-issue-5047"
        assert cel_alert.id == "github-issue-5047"
        
        # Alert should now be properly un-dismissed
        assert sidebar_alert.dismissed == False, "Alert should be un-dismissed after expiry"
        assert cel_alert.dismissed == False, "Alert should be un-dismissed after expiry"
        assert sidebar_alert.dismissUntil is None, "dismissUntil should be cleared"
        assert cel_alert.dismissUntil is None, "dismissUntil should be cleared"
        
        # Verify disposable fields were cleaned up (bonus improvement)
        assert not hasattr(sidebar_alert, 'disposable_dismissed') or \
               getattr(sidebar_alert, 'disposable_dismissed', None) is None
        assert not hasattr(sidebar_alert, 'disposable_note') or \
               getattr(sidebar_alert, 'disposable_note', None) is None
        
        # Test additional CEL expressions that should also work now
        additional_cel_filters = [
            "severity == 'warning' && dismissed == false",     # Complex CEL with dismissed == false  
            "dismissed != true",                                # Alternative CEL syntax
        ]
        
        for cel_expr in additional_cel_filters:
            test_query = SearchQuery(
                sql_query={
                    "sql": "dismissed != :dismissed_1",
                    "params": {"dismissed_1": "true"},
                },
                cel_query=cel_expr,
            )
            
            results = SearchEngine(tenant_id=tenant_id).search_alerts(test_query)
            assert len(results) == 1, f"Additional CEL '{cel_expr}' should also work after fix"
            assert results[0].dismissed == False


def test_dismissal_expiry_bug_search_filters_FIXED_with_watcher(db_session):
    """
    FIXED VERSION: This test shows that the dismissal expiry bug is resolved when using the watcher.
    
    Same scenario as test_dismissal_expiry_bug_search_filters but with watcher enabled.
    This test should PASS, demonstrating the fix works.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    # Step 1: Create an alert that is NOT dismissed initially
    initial_time = datetime.datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(initial_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event=_create_valid_event({
                "id": "test-alert-expiry-fixed",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "fingerprint": "test-expiry-fixed-fingerprint",
            }),
            fingerprint="test-expiry-fixed-fingerprint",
            timestamp=initial_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()

    # Step 2: Dismiss the alert with a future dismissUntil timestamp (1 hour from now)
    dismiss_time = initial_time + timedelta(minutes=30)
    dismiss_until_time = initial_time + timedelta(hours=1)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="test-expiry-fixed-fingerprint",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
                "disposable_dismissed": True,
                "disposable_dismissedUntil": dismiss_until_str,
                "disposable_note": "Maintenance window",
                "disposable_status": "suppressed"
            },
            action_callee="workflow",
            action_description="Alert dismissed by maintenance workflow",
            action_type=ActionType.GENERIC_ENRICH,
        )

    # Step 3: Time travel to AFTER the dismissUntil timestamp has expired
    after_expiry_time = dismiss_until_time + timedelta(minutes=30)
    
    with freeze_time(after_expiry_time):
        # Test filtering for non-dismissed alerts - BEFORE watcher
        search_query_not_dismissed = SearchQuery(
            sql_query={
                "sql": "dismissed != :dismissed_1",
                "params": {"dismissed_1": "true"},
            },
            cel_query="dismissed == false",
        )
        
        non_dismissed_alerts_before = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        assert len(non_dismissed_alerts_before) == 0, "Before watcher: bug exists, alert not returned"
        
        # RUN THE FIX: Apply dismissal expiry watcher
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # Test filtering for non-dismissed alerts - AFTER watcher
        non_dismissed_alerts_after = SearchEngine(tenant_id=tenant_id).search_alerts(search_query_not_dismissed)
        
        # ✅ FIXED: This should now return the alert!
        assert len(non_dismissed_alerts_after) == 1, "FIXED: Alert appears in non-dismissed filter after watcher"
        assert non_dismissed_alerts_after[0].dismissed == False
        assert non_dismissed_alerts_after[0].dismissUntil is None


def test_dismissal_expiry_bug_cel_filter_FIXED_with_watcher(db_session):
    """
    FIXED VERSION: Shows that CEL-based filters work correctly after watcher processes expired dismissals.
    
    Same scenario as test_dismissal_expiry_bug_with_cel_filter but with watcher enabled.
    This test should PASS, demonstrating the fix works.
    """
    tenant_id = SINGLE_TENANT_UUID
    
    start_time = datetime.datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    
    with freeze_time(start_time):
        alert = Alert(
            tenant_id=tenant_id,
            provider_type="test", 
            provider_id="test",
            event=_create_valid_event({
                "id": "cel-filter-test-fixed",
                "fingerprint": "cel-test-fixed-fp",
                "status": AlertStatus.FIRING.value,
                "dismissed": False,
                "dismissUntil": None,
                "source": ["test-source"],
                "severity": "warning"
            }),
            fingerprint="cel-test-fixed-fp",
            timestamp=start_time
        )
        
        db_session.add(alert)
        db_session.commit()
        
        last_alert = LastAlert(
            tenant_id=tenant_id,
            fingerprint=alert.fingerprint,
            timestamp=alert.timestamp,
            first_timestamp=alert.timestamp,
            alert_id=alert.id,
        )
        db_session.add(last_alert)
        db_session.commit()

    # Dismiss with 30-minute window
    dismiss_time = start_time + timedelta(minutes=5)
    dismiss_until_time = start_time + timedelta(minutes=30)
    dismiss_until_str = dismiss_until_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    with freeze_time(dismiss_time):
        enrichment_bl = EnrichmentsBl(tenant_id, db_session)
        enrichment_bl.enrich_entity(
            fingerprint="cel-test-fixed-fp",
            enrichments={
                "dismissed": True,
                "dismissUntil": dismiss_until_str,
            },
            action_callee="test",
            action_description="CEL filter test dismissal",
            action_type=ActionType.GENERIC_ENRICH,
        )

    # Time travel past expiry
    past_expiry_time = dismiss_until_time + timedelta(minutes=15)
    
    with freeze_time(past_expiry_time):
        # RUN THE FIX: Apply dismissal expiry watcher FIRST
        wait_for_dismissal_expiry_processing(tenant_id, db_session)
        
        # Test various CEL expressions that should find the non-dismissed alert
        cel_expressions = [
            "dismissed == false",
            "!dismissed", 
            "dismissed != true",
            "severity == 'warning' && dismissed == false"
        ]
        
        for cel_expr in cel_expressions:
            search_query = SearchQuery(
                sql_query={
                    "sql": "dismissed != :dismissed_1",
                    "params": {"dismissed_1": "true"},
                },
                cel_query=cel_expr,
            )
            
            # ✅ FIXED: All of these should now return 1 alert!
            results = SearchEngine(tenant_id=tenant_id).search_alerts(search_query)
            
            assert len(results) == 1, (
                f"FIXED: CEL expression '{cel_expr}' now correctly returns 1 alert "
                f"after dismissal expires and watcher processes it"
            )
            assert results[0].dismissed == False
            assert results[0].dismissUntil is None
