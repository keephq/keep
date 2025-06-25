import datetime
import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.workflow import Workflow

from tests.fixtures.workflow_manager import workflow_manager  # noqa


@pytest.fixture
def create_workflow(db_session):
    """Fixture to create a workflow with a specific CEL expression"""

    def _create_workflow(workflow_id, cel_expression):
        workflow_definition = f"""workflow:
  id: {workflow_id}
  description: Test CEL severity expressions
  triggers:
    - type: alert
      cel: {cel_expression}
  actions:
    - name: test-action
      provider:
        type: console
        with:
          message: "Alert matched CEL expression"
"""
        workflow = Workflow(
            id=workflow_id,
            name=workflow_id,
            tenant_id=SINGLE_TENANT_UUID,
            description="Test CEL severity expressions",
            created_by="test@keephq.dev",
            interval=0,
            workflow_raw=workflow_definition,
        )
        db_session.add(workflow)
        db_session.commit()
        return workflow

    return _create_workflow


@pytest.fixture
def create_alert():
    """Fixture to create test alerts with different severities"""

    def _create_alert(**kwargs):
        default_alert = {
            "name": "test-alert",
            "source": ["prometheus"],
            "status": AlertStatus.FIRING,
            "severity": AlertSeverity.INFO,
            "fingerprint": f"fp-{datetime.datetime.now().isoformat()}",
            "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        default_alert.update(kwargs)
        return AlertDto(**default_alert)

    return _create_alert


def test_severity_greater_than_info_matches_high_and_critical(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test the specific bug case: severity > 'info' should match 'high' and 'critical' severities"""
    # Create a workflow with the exact CEL expression from the bug report
    workflow = create_workflow("test-severity-greater-than-info", "severity > 'info' && source.contains('prometheus')")

    # Create alerts that should match
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")

    # Create alerts that should NOT match
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")

    # Test high severity alert (should match)
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [high_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Test critical severity alert (should match)
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [critical_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Test warning severity alert (should match)
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [warning_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Test info severity alert (should NOT match)
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [info_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    # Test low severity alert (should NOT match)
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [low_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_greater_than_or_equal_warning(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test severity >= 'warning' comparisons"""
    workflow = create_workflow("test-severity-gte-warning", "severity >= 'warning'")

    # Should match: critical, high, warning
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")

    # Should NOT match: info, low
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")

    # Test matching severities
    for alert in [critical_alert, high_alert, warning_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching severities
    for alert in [info_alert, low_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_less_than_warning(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test severity < 'warning' comparisons"""
    workflow = create_workflow("test-severity-lt-warning", "severity < 'warning'")

    # Should match: info, low
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")

    # Should NOT match: warning, high, critical
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")

    # Test matching severities
    for alert in [info_alert, low_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching severities
    for alert in [warning_alert, high_alert, critical_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_less_than_or_equal_high(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test severity <= 'high' comparisons"""
    workflow = create_workflow("test-severity-lte-high", "severity <= 'high'")

    # Should match: low, info, warning, high
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")

    # Should NOT match: critical
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")

    # Test matching severities
    for alert in [low_alert, info_alert, warning_alert, high_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching severities
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [critical_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_equality_critical(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test severity == 'critical' comparisons"""
    workflow = create_workflow("test-severity-eq-critical", "severity == 'critical'")

    # Should match: only critical
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")

    # Should NOT match: all others
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")

    # Test matching severity
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [critical_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching severities
    for alert in [high_alert, warning_alert, info_alert, low_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_complex_severity_conditions(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test complex CEL expressions involving severity comparisons"""
    workflow = create_workflow(
        "test-complex-severity",
        "(severity >= 'warning' && source.contains('prometheus')) || (severity == 'critical' && source.contains('grafana'))"
    )

    # Should match: prometheus with warning+, grafana with critical
    prometheus_critical = create_alert(
        severity=AlertSeverity.CRITICAL, source=["prometheus"], fingerprint="fp1"
    )
    prometheus_high = create_alert(
        severity=AlertSeverity.HIGH, source=["prometheus"], fingerprint="fp2"
    )
    prometheus_warning = create_alert(
        severity=AlertSeverity.WARNING, source=["prometheus"], fingerprint="fp3"
    )
    grafana_critical = create_alert(
        severity=AlertSeverity.CRITICAL, source=["grafana"], fingerprint="fp4"
    )

    # Should NOT match: prometheus with info/low, grafana with non-critical
    prometheus_info = create_alert(
        severity=AlertSeverity.INFO, source=["prometheus"], fingerprint="fp5"
    )
    grafana_high = create_alert(
        severity=AlertSeverity.HIGH, source=["grafana"], fingerprint="fp6"
    )

    # Test matching alerts
    for alert in [prometheus_critical, prometheus_high, prometheus_warning, grafana_critical]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching alerts
    for alert in [prometheus_info, grafana_high]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_boundary_conditions(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test boundary conditions for severity comparisons"""
    
    # Test severity > 'critical' (should never match)
    workflow_never_match = create_workflow("test-severity-gt-critical", "severity > 'critical'")
    
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [critical_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before
    
    # Test severity < 'low' (should never match)
    workflow_never_match_2 = create_workflow("test-severity-lt-low", "severity < 'low'")
    
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [low_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_case_sensitivity_in_severity_comparisons(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test that severity comparisons are case-insensitive"""
    workflow = create_workflow("test-severity-case", "severity > 'INFO'")

    # Should match despite case difference
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [high_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    
    # Test with different case variations
    workflow_mixed_case = create_workflow("test-severity-mixed-case", "severity >= 'Warning'")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")
    
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [warning_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1