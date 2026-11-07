"""
Unit tests for CEL severity in list preprocessing and maintenance windows severity handling.

Reproduces and verifies the fix for https://github.com/keephq/keep/issues/6850:
- severity in ['critical', 'high'] is rewritten to numeric orders (e.g. severity in [5, 4]).
- MaintenanceWindowsBl.evaluate_cel normalizes alert severity to numeric orders and does
  not mutate stored alert events.
"""

from unittest.mock import MagicMock
import celpy

from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.models.alert import AlertDto, AlertSeverity
from keep.api.models.db.alert import Alert
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.utils.cel_utils import preprocess_cel_expression


def test_preprocess_cel_expression_severity_in_list():
    """Verify that severity in [...] lists are rewritten to numeric orders."""
    assert (
        preprocess_cel_expression("severity in ['critical', 'high']")
        == "severity in [5, 4]"
    )
    assert (
        preprocess_cel_expression('severity in ["low", "warning"]')
        == "severity in [1, 3]"
    )
    assert preprocess_cel_expression("severity in ['CRITICAL']") == "severity in [5]"
    assert (
        preprocess_cel_expression(
            "severity in ['critical', 'high'] && service == 'auth'"
        )
        == "severity in [5, 4] && service == 'auth'"
    )


def test_preprocess_cel_expression_standard_comparisons_preserved():
    """Verify that standard binary comparisons continue to be rewritten correctly."""
    assert preprocess_cel_expression("severity == 'critical'") == "severity == 5"
    assert preprocess_cel_expression("severity >= 'high'") == "severity >= 4"
    assert preprocess_cel_expression("severity != 'low'") == "severity != 1"
    assert (
        preprocess_cel_expression("status in ['firing', 'resolved']")
        == "status in ['firing', 'resolved']"
    )


def test_evaluate_cel_maintenance_window_severity_comparison():
    """Verify that evaluate_cel properly evaluates numeric severity comparisons on AlertDto."""
    env = celpy.Environment()
    logger = MagicMock()

    rule = MaintenanceWindowRule(
        name="test-mw",
        tenant_id="test-tenant",
        cel_query="severity == 'critical'",
    )
    alert = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        severity=AlertSeverity.CRITICAL,
        source=["test"],
    )

    result = MaintenanceWindowsBl.evaluate_cel(rule, alert, env, logger, {})
    assert result is True


def test_evaluate_cel_maintenance_window_severity_in_list():
    """Verify that evaluate_cel properly evaluates severity in [...] on AlertDto."""
    env = celpy.Environment()
    logger = MagicMock()

    rule = MaintenanceWindowRule(
        name="test-mw",
        tenant_id="test-tenant",
        cel_query="severity in ['critical', 'high']",
    )
    alert_high = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        severity=AlertSeverity.HIGH,
        source=["test"],
    )
    alert_low = AlertDto(
        name="test-alert",
        lastReceived="2024-01-01T00:00:00Z",
        severity=AlertSeverity.LOW,
        source=["test"],
    )

    assert MaintenanceWindowsBl.evaluate_cel(rule, alert_high, env, logger, {}) is True
    assert MaintenanceWindowsBl.evaluate_cel(rule, alert_low, env, logger, {}) is False


def test_evaluate_cel_preserves_db_alert_event_structure():
    """Verify that evaluate_cel does not mutate the original Alert.event dictionary."""
    env = celpy.Environment()
    logger = MagicMock()

    rule = MaintenanceWindowRule(
        name="test-mw",
        tenant_id="test-tenant",
        cel_query="severity == 'critical'",
    )
    original_event = {
        "name": "test-alert",
        "severity": "critical",
        "source": ["test"],
    }
    db_alert = Alert(
        tenant_id="test-tenant",
        provider_type="keep",
        provider_id="keep",
        event=original_event,
        fingerprint="fp-1",
    )

    result = MaintenanceWindowsBl.evaluate_cel(rule, db_alert, env, logger, {})
    assert result is True
    # The original event dictionary in db_alert must retain its original string severity
    assert db_alert.event["severity"] == "critical"
