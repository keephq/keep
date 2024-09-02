from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from keep.api.bl.blackouts_bl import BlackoutsBl
from keep.api.models.alert import AlertDto
from keep.api.models.db.blackout import BlackoutRule


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def active_blackout_rule():
    return BlackoutRule(
        id=1,
        name="Active Blackout",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(hours=1),
        enabled=True,
    )


@pytest.fixture
def expired_blackout_rule():
    return BlackoutRule(
        id=2,
        name="Expired Blackout",
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


def test_alert_in_active_blackout(mock_session, active_blackout_rule, alert_dto):
    # Simulate the query to return the active blackout
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    assert result is True


def test_alert_not_in_expired_blackout(mock_session, expired_blackout_rule, alert_dto):
    # Simulate the query to return the expired blackout
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        expired_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    # Even though the query returned a blackout, it should not match because it's expired
    assert result is False


def test_alert_in_no_blackout(mock_session, alert_dto):
    # Simulate the query to return no blackouts
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = (
        []
    )

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    assert result is False


def test_alert_in_blackout_with_non_matching_cel(
    mock_session, active_blackout_rule, alert_dto
):
    # Modify the cel_query so that the alert won't match
    active_blackout_rule.cel_query = 'source == "other-source"'
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    assert result is False


def test_alert_ignored_due_to_resolved_status(
    mock_session, active_blackout_rule, alert_dto
):
    # Set the alert status to RESOLVED
    alert_dto.status = "resolved"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    # Should return False because the alert status is RESOLVED
    assert result is False


def test_alert_ignored_due_to_acknowledged_status(
    mock_session, active_blackout_rule, alert_dto
):
    # Set the alert status to ACKNOWLEDGED
    alert_dto.status = "acknowledged"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    # Should return False because the alert status is ACKNOWLEDGED
    assert result is False
