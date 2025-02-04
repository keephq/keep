from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.maintenance_window import MaintenanceWindowRule


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def active_maintenance_window_rule():
    return MaintenanceWindowRule(
        id=1,
        name="Active maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        enabled=True,
    )


@pytest.fixture
def active_maintenance_window_rule_with_suppression_on():
    return MaintenanceWindowRule(
        id=1,
        name="Active maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        enabled=True,
        suppress=True,
    )


@pytest.fixture
def expired_maintenance_window_rule():
    return MaintenanceWindowRule(
        id=2,
        name="Expired maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(days=2),
        end_time=datetime.utcnow() - timedelta(days=1),
        enabled=True,
    )


@pytest.fixture
def alert_dto():
    return AlertDto(
        id="test-alert",
        source=["test-source"],
        name="Test Alert",
        status="firing",
        severity="critical",
        lastReceived="2021-08-01T00:00:00Z",
    )


def test_alert_in_active_maintenance_window(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Simulate the query to return the active maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is True


def test_alert_in_active_maintenance_window_with_suppress(
    mock_session, active_maintenance_window_rule_with_suppression_on, alert_dto
):
    # Simulate the query to return the active maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule_with_suppression_on
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False
    assert alert_dto.status == AlertStatus.SUPPRESSED.value


def test_alert_not_in_expired_maintenance_window(
    mock_session, expired_maintenance_window_rule, alert_dto
):
    # Simulate the query to return the expired maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        expired_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Even though the query returned a maintenance_window, it should not match because it's expired
    assert result is False


def test_alert_in_no_maintenance_window(mock_session, alert_dto):
    # Simulate the query to return no maintenance_windows
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = (
        []
    )

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False


def test_alert_in_maintenance_window_with_non_matching_cel(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Modify the cel_query so that the alert won't match
    active_maintenance_window_rule.cel_query = 'source == "other-source"'
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False


def test_alert_ignored_due_to_resolved_status(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Set the alert status to RESOLVED
    alert_dto.status = "resolved"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the alert status is RESOLVED
    assert result is False


def test_alert_ignored_due_to_acknowledged_status(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Set the alert status to ACKNOWLEDGED
    alert_dto.status = "acknowledged"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the alert status is ACKNOWLEDGED
    assert result is False


def test_alert_with_missing_cel_field(mock_session, active_maintenance_window_rule, alert_dto):
    # Modify the cel_query to reference a non-existent field
    active_maintenance_window_rule.cel_query = 'alertname == "test-alert"'
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the field doesn't exist
    assert result is False
