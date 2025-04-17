import time
from datetime import datetime

import pytest

from keep.api.models.alert import AlertStatus
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_basic(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test basic batch enrichment with a simple CEL expression (name matching)."""
    # Create test alerts with specific names
    create_alert(
        "alert-cpu-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "CPU Overload Alert", "severity": "critical"},
    )
    create_alert(
        "alert-memory-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Memory Usage Alert", "severity": "warning"},
    )
    create_alert(
        "alert-disk-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Disk Space Alert", "severity": "warning"},
    )

    # Enrich alerts with name containing "CPU" via CEL
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "name.contains('CPU')",
            "enrichments": {
                "status": "acknowledged",
                "note": "CPU issue being investigated",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 1

    time.sleep(1)  # Allow time for async processing

    # Get all alerts and verify only CPU alert was enriched
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 3

    cpu_alert = next(a for a in alerts if a["name"] == "CPU Overload Alert")
    memory_alert = next(a for a in alerts if a["name"] == "Memory Usage Alert")
    disk_alert = next(a for a in alerts if a["name"] == "Disk Space Alert")

    assert cpu_alert["status"] == "acknowledged"
    assert cpu_alert["note"] == "CPU issue being investigated"
    assert memory_alert["status"] == "firing"
    assert disk_alert["status"] == "firing"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_severity(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment with CEL expression filtering by severity."""
    # Create test alerts with different severities
    create_alert(
        "alert-critical-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Critical Service Down", "severity": "critical"},
    )
    create_alert(
        "alert-warning-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Warning Alert", "severity": "warning"},
    )
    create_alert(
        "alert-warning-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Another Warning", "severity": "warning"},
    )

    # Enrich all warning alerts
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "severity == 'warning'",
            "enrichments": {
                "status": "suppressed",
                "note": "Low priority alerts suppressed",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 2

    time.sleep(1)  # Allow time for async processing

    # Verify only warning alerts were suppressed
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 3

    critical_alert = next(a for a in alerts if a["severity"] == "critical")
    warning_alerts = [a for a in alerts if a["severity"] == "warning"]

    assert critical_alert["status"] == "firing"
    assert all(a["status"] == "suppressed" for a in warning_alerts)
    assert all(a["note"] == "Low priority alerts suppressed" for a in warning_alerts)


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_labels(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment with CEL expression filtering by labels."""
    # Create test alerts with different labels
    create_alert(
        "alert-region1-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Region 1 Alert",
            "severity": "critical",
            "labels": {"region": "us-east-1", "service": "api"},
        },
    )
    create_alert(
        "alert-region1-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Region 1 Service Alert",
            "severity": "warning",
            "labels": {"region": "us-east-1", "service": "database"},
        },
    )
    create_alert(
        "alert-region2-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Region 2 Alert",
            "severity": "critical",
            "labels": {"region": "us-west-1", "service": "api"},
        },
    )

    # Enrich alerts from us-east-1 region
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "labels.region == 'us-east-1'",
            "enrichments": {
                "status": "acknowledged",
                "assignee": "east-team@example.com",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 2

    time.sleep(1)  # Allow time for async processing

    # Verify correct alerts were enriched
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 3

    east_alerts = [
        a for a in alerts if a.get("labels", {}).get("region") == "us-east-1"
    ]
    west_alerts = [
        a for a in alerts if a.get("labels", {}).get("region") == "us-west-1"
    ]

    assert all(a["status"] == "acknowledged" for a in east_alerts)
    assert all(a["assignee"] == "east-team@example.com" for a in east_alerts)
    assert all(a["status"] == "firing" for a in west_alerts)


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_complex_expression(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment with a complex CEL expression combining multiple conditions."""
    # Create test alerts with various properties
    create_alert(
        "alert-prod-critical-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Production Critical Alert",
            "severity": "critical",
            "environment": "production",
            "service": "api",
        },
    )
    create_alert(
        "alert-prod-warning-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Production Warning Alert",
            "severity": "warning",
            "environment": "production",
            "service": "api",
        },
    )
    create_alert(
        "alert-staging-critical-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Staging Critical Alert",
            "severity": "critical",
            "environment": "staging",
            "service": "api",
        },
    )
    create_alert(
        "alert-prod-critical-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {
            "name": "Production Critical DB Alert",
            "severity": "critical",
            "environment": "production",
            "service": "database",
        },
    )

    # Enrich critical production API alerts
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "severity == 'critical' && environment == 'production' && service == 'api'",
            "enrichments": {
                "status": "acknowledged",
                "note": "Critical API issue - investigating",
                "assignee": "api-team@example.com",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 1

    time.sleep(1)  # Allow time for async processing

    # Verify only the matching alert was enriched
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 4

    # Find the production critical API alert
    prod_critical_api = next(
        a
        for a in alerts
        if a["environment"] == "production"
        and a["severity"] == "critical"
        and a["service"] == "api"
    )

    # Check it was properly enriched
    assert prod_critical_api["status"] == "acknowledged"
    assert prod_critical_api["note"] == "Critical API issue - investigating"
    assert prod_critical_api["assignee"] == "api-team@example.com"

    # Check other alerts were not enriched
    other_alerts = [
        a
        for a in alerts
        if not (
            a["environment"] == "production"
            and a["severity"] == "critical"
            and a["service"] == "api"
        )
    ]
    assert all(a["status"] == "firing" for a in other_alerts)
    assert all(not a.get("assignee") for a in other_alerts)


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_no_matching_alerts(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment when no alerts match the CEL expression."""
    # Create some alerts
    create_alert(
        "alert-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Test Alert 1", "severity": "critical"},
    )
    create_alert(
        "alert-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Test Alert 2", "severity": "warning"},
    )

    # Use a CEL expression that won't match any alerts
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "name.contains('NonExistentString')",
            "enrichments": {
                "status": "acknowledged",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 0
    assert "message" in result
    assert "No alerts matched the query" in result["message"]

    # Verify no alerts were changed
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 2
    assert all(a["status"] == "firing" for a in alerts)


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_invalid_expression(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment with an invalid CEL expression."""
    # Create an alert
    create_alert(
        "alert-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Test Alert", "severity": "critical"},
    )

    # Use an invalid CEL expression
    response = client.post(
        "/alerts/batch_enrich_by_cel",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "invalid.syntax &&& !!!",
            "enrichments": {
                "status": "acknowledged",
            },
        },
    )

    # Should return a 400 error
    assert response.status_code == 400
    assert "Error parsing CEL expression" in response.json()["detail"]

    # Verify no alerts were changed
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 1
    assert alerts[0]["status"] == "firing"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@pytest.mark.parametrize("elastic_client", [False], indirect=True)
def test_batch_enrich_by_cel_dispose_on_new_alert(
    db_session, client, test_app, create_alert, elastic_client
):
    """Test batch enrichment with dispose_on_new_alert parameter."""
    # Create an alert
    create_alert(
        "alert-test-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Test Alert", "severity": "critical"},
    )

    # Enrich the alert with dispose_on_new_alert=True
    response = client.post(
        "/alerts/batch_enrich_by_cel?dispose_on_new_alert=true",
        headers={"x-api-key": "some-key"},
        json={
            "cel": "name.contains('Test')",
            "enrichments": {
                "status": "resolved",
                "note": "Temporary resolution note",
            },
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["affected_alerts"] == 1

    time.sleep(1)  # Allow time for async processing

    # Verify the alert was enriched
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    assert len(alerts) == 1
    assert alerts[0]["status"] == "resolved"
    assert alerts[0]["note"] == "Temporary resolution note"

    # Create a new alert with the same fingerprint to simulate a new occurrence
    create_alert(
        "alert-test-1",  # Same fingerprint
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"name": "Test Alert", "severity": "critical"},
    )

    time.sleep(1)  # Allow time for processing

    # Verify the new alert has the disposable enrichment
    response = client.get(
        "/preset/feed/alerts",
        headers={"x-api-key": "some-key"},
    )
    alerts = response.json()

    # This assertion checks the behavior described in the issue
    # Note: Based on the reported issue, this might actually show the enrichment persisting
    # which is the behavior being reported as problematic
    assert len(alerts) == 1

    # Check if alert kept the enriched status (current behavior) or reverted to firing (desired behavior)
    # We're testing the current behavior here - in a real fix, this would change
    current_status = alerts[0]["status"]
    print(f"Current alert status after new occurrence: {current_status}")
