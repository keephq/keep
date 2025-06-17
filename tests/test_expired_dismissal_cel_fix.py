import datetime
import json
import time
from datetime import timezone

import pytest
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
def test_cleanup_expired_dismissals_function(
    db_session, test_app, create_alert
):
    """Test that the cleanup_expired_dismissals function correctly updates expired dismissals."""
    # Create an alert
    fingerprint = "test-expired-dismissal"
    create_alert(
        fingerprint,
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Test Alert for Dismissal",
            "severity": "critical",
            "service": "test-service",
        },
    )
    
    # Create enrichment that dismisses the alert until a past time (expired dismissal)
    past_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    enrichment_bl = EnrichmentsBl("keep", db=db_session)
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint,
        enrichments={
            "dismissed": True,
            "dismissedUntil": past_time,
            "note": "Temporarily dismissed"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test dismissal"
    )
    
    # Verify the alert is initially dismissed in the database
    from keep.api.core.db import get_enrichment
    enrichment = get_enrichment("keep", fingerprint)
    assert enrichment.enrichments["dismissed"] is True
    assert enrichment.enrichments["dismissedUntil"] == past_time
    
    # Run the cleanup function
    cleanup_expired_dismissals("keep", db_session)
    
    # Verify the dismissal was cleaned up
    enrichment = get_enrichment("keep", fingerprint)
    assert enrichment.enrichments["dismissed"] is False
    assert enrichment.enrichments["dismissedUntil"] == past_time  # dismissedUntil should remain unchanged


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_cel_filtering_with_expired_dismissal(
    db_session, test_app, create_alert
):
    """Test that CEL filtering correctly handles expired dismissals."""
    # Create two alerts
    fingerprint1 = "test-alert-1"
    create_alert(
        fingerprint1,
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Alert 1",
            "severity": "critical",
            "service": "service-1",
        },
    )
    
    fingerprint2 = "test-alert-2"
    create_alert(
        fingerprint2, 
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Alert 2",
            "severity": "warning",
            "service": "service-2",
        },
    )
    
    # Dismiss alert1 with an expired dismissedUntil (past time)
    past_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Dismiss alert2 with a future dismissedUntil (active dismissal)
    future_time = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    enrichment_bl = EnrichmentsBl("keep", db=db_session)
    
    # Dismiss alert1 with expired time
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint1,
        enrichments={
            "dismissed": True,
            "dismissedUntil": past_time,
            "note": "Expired dismissal"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test expired dismissal"
    )
    
    # Dismiss alert2 with future time
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint2,
        enrichments={
            "dismissed": True,
            "dismissedUntil": future_time,
            "note": "Active dismissal"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test active dismissal"
    )
    
    # Test CEL filter for dismissed == false
    # This should return alert1 (expired dismissal) but not alert2 (active dismissal)
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    
    # Should find alert1 (expired dismissal should be treated as not dismissed)
    # Should NOT find alert2 (still actively dismissed)
    assert len(alerts_dto) == 1
    assert alerts_dto[0].fingerprint == fingerprint1
    assert alerts_dto[0].dismissed is False  # Should be False due to expiration
    
    # Test CEL filter for dismissed == true
    # This should return alert2 (active dismissal) but not alert1 (expired dismissal)
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    
    # Should find alert2 (active dismissal)
    # Should NOT find alert1 (expired dismissal)
    assert len(alerts_dto) == 1
    assert alerts_dto[0].fingerprint == fingerprint2
    assert alerts_dto[0].dismissed is True  # Should still be True as not expired


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_cel_filtering_with_non_expired_dismissal(
    db_session, test_app, create_alert
):
    """Test that non-expired dismissals still work correctly."""
    # Create an alert
    fingerprint = "test-non-expired"
    create_alert(
        fingerprint,
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Test Alert",
            "severity": "warning",
        },
    )
    
    # Dismiss with future time (active dismissal)
    future_time = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    enrichment_bl = EnrichmentsBl("keep", db=db_session)
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint,
        enrichments={
            "dismissed": True,
            "dismissedUntil": future_time,
            "note": "Active dismissal"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test active dismissal"
    )
    
    # CEL filter for dismissed == true should find this alert
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    assert len(alerts_dto) == 1
    assert alerts_dto[0].fingerprint == fingerprint
    assert alerts_dto[0].dismissed is True
    
    # CEL filter for dismissed == false should NOT find this alert
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    assert len(alerts_dto) == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_cel_filtering_with_forever_dismissal(
    db_session, test_app, create_alert
):
    """Test that 'forever' dismissals work correctly."""
    # Create an alert
    fingerprint = "test-forever-dismissal"
    create_alert(
        fingerprint,
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Test Alert Forever",
            "severity": "info",
        },
    )
    
    # Dismiss forever
    enrichment_bl = EnrichmentsBl("keep", db=db_session)
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint,
        enrichments={
            "dismissed": True,
            "dismissedUntil": "forever",
            "note": "Forever dismissal"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test forever dismissal"
    )
    
    # CEL filter for dismissed == true should find this alert
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == true", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    assert len(alerts_dto) == 1
    assert alerts_dto[0].fingerprint == fingerprint
    assert alerts_dto[0].dismissed is True
    
    # CEL filter for dismissed == false should NOT find this alert
    db_alerts, total_count = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="dismissed == false", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    assert len(alerts_dto) == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_rules_engine_cel_filtering_with_expired_dismissal(
    db_session, test_app, create_alert
):
    """Test that RulesEngine CEL filtering works correctly with expired dismissals."""
    # Create an alert
    fingerprint = "test-rules-engine"
    create_alert(
        fingerprint,
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "Rules Engine Test Alert",
            "severity": "high",
        },
    )
    
    # Dismiss with expired time
    past_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    enrichment_bl = EnrichmentsBl("keep", db=db_session)
    enrichment_bl.enrich_entity(
        fingerprint=fingerprint,
        enrichments={
            "dismissed": True,
            "dismissedUntil": past_time,
            "note": "Expired dismissal for rules engine test"
        },
        action_type=ActionType.GENERIC_ENRICH,
        action_callee="test_user",
        action_description="Test rules engine dismissal"
    )
    
    # Get alerts as DTOs (this should apply the validation logic)
    db_alerts, _ = query_last_alerts(
        tenant_id="keep",
        query=QueryDto(cel="", limit=100, sort_by="timestamp", sort_dir="desc", sort_options=[])
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(db_alerts)
    
    # Use RulesEngine to filter alerts (Python-based CEL filtering)
    rules_engine = RulesEngine("keep")
    
    # Filter for dismissed == false (should find the alert with expired dismissal)
    filtered_not_dismissed = rules_engine.filter_alerts(alerts_dto, "dismissed == false")
    assert len(filtered_not_dismissed) == 1
    assert filtered_not_dismissed[0].fingerprint == fingerprint
    assert filtered_not_dismissed[0].dismissed is False
    
    # Filter for dismissed == true (should NOT find the alert with expired dismissal)
    filtered_dismissed = rules_engine.filter_alerts(alerts_dto, "dismissed == true")
    assert len(filtered_dismissed) == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_api_endpoint_with_expired_dismissal_cel(
    db_session, client, test_app, create_alert
):
    """Test that API endpoints correctly handle expired dismissal CEL queries."""
    # Create alerts
    alert1 = create_alert(
        "api-test-alert-1",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "API Test Alert 1",
            "severity": "critical",
        },
    )
    
    alert2 = create_alert(
        "api-test-alert-2",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "name": "API Test Alert 2", 
            "severity": "warning",
        },
    )
    
    # Dismiss alert1 with expired time
    past_time = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Dismiss alert2 with future time
    future_time = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Use the batch_enrich API to dismiss alerts
    response = client.post(
        "/alerts/batch_enrich",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprints": [alert1.fingerprint],
            "enrichments": {
                "dismissed": "true",
                "dismissedUntil": past_time,
                "note": "Expired dismissal"
            },
        },
    )
    assert response.status_code == 200
    
    response = client.post(
        "/alerts/batch_enrich", 
        headers={"x-api-key": "some-key"},
        json={
            "fingerprints": [alert2.fingerprint],
            "enrichments": {
                "dismissed": "true",
                "dismissedUntil": future_time,
                "note": "Active dismissal"
            },
        },
    )
    assert response.status_code == 200
    
    time.sleep(1)  # Allow time for processing
    
    # Query for non-dismissed alerts using CEL
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
    
    # Should find alert1 (expired dismissal) but not alert2 (active dismissal)
    assert result["count"] == 1
    found_alert = result["results"][0]
    assert found_alert["fingerprint"] == alert1.fingerprint
    assert found_alert["dismissed"] is False
    
    # Query for dismissed alerts using CEL
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
    
    # Should find alert2 (active dismissal) but not alert1 (expired dismissal)
    assert result["count"] == 1
    found_alert = result["results"][0]
    assert found_alert["fingerprint"] == alert2.fingerprint
    assert found_alert["dismissed"] is True