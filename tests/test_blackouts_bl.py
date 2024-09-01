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
def mock_blackout_rule():
    return BlackoutRule(
        id=1,
        name="Test Blackout",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(hours=1),
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


def test_alert_in_blackout(mock_session, mock_blackout_rule, alert_dto):
    mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = [
        mock_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    assert result is True


def test_alert_not_in_blackout(mock_session, mock_blackout_rule, alert_dto):
    # Modify the cel_query so that the alert won't match
    mock_blackout_rule.cel_query = 'source == "other-source"'
    mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = [
        mock_blackout_rule
    ]

    blackout_bl = BlackoutsBl(tenant_id="test-tenant", session=mock_session)
    result = blackout_bl.check_if_alert_in_blackout(alert_dto)

    assert result is False
