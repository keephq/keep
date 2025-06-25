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
  description: Test severity CEL expressions
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
            description="Test severity CEL expressions",
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
    """Fixture to create an alert DTO with specified properties"""

    def _create_alert(**properties):
        alert_data = {
            "id": "test-alert-1",
            "source": ["prometheus"],
            "name": "test-alert",
            "status": AlertStatus.FIRING,
            "severity": AlertSeverity.INFO,
            "lastReceived": datetime.datetime.now().isoformat(),
            "fingerprint": f"test-fingerprint-{datetime.datetime.now().timestamp()}",
        }
        alert_data.update(properties)
        return AlertDto(**alert_data)

    return _create_alert


def test_severity_greater_than_info_bug_fix(
    db_session, workflow_manager, create_workflow, create_alert
):
    """
    Test the specific bug case from GitHub issue #5086:
    severity > 'info' should match 'warning', 'high', and 'critical' severities
    
    Before fix: This would fail because 'high' < 'info' lexicographically (h < i)
    After fix: This works because high (4) > info (2) numerically
    """
    # Create a workflow with the exact CEL expression from the bug report
    workflow = create_workflow(
        "test-severity-gt-info-bug", 
        "severity > 'info' && source.contains('prometheus')"
    )

    # These alerts should match (severity > info)
    high_alert = create_alert(
        severity=AlertSeverity.HIGH, 
        fingerprint="fp-high"
    )
    critical_alert = create_alert(
        severity=AlertSeverity.CRITICAL, 
        fingerprint="fp-critical"
    )
    warning_alert = create_alert(
        severity=AlertSeverity.WARNING, 
        fingerprint="fp-warning"
    )

    # These alerts should NOT match
    info_alert = create_alert(
        severity=AlertSeverity.INFO, 
        fingerprint="fp-info"
    )
    low_alert = create_alert(
        severity=AlertSeverity.LOW, 
        fingerprint="fp-low"
    )

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
    """Test severity >= 'warning' comparisons work correctly with numeric conversion"""
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


def test_severity_less_than_high(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test severity < 'high' comparisons work correctly with numeric conversion"""
    workflow = create_workflow("test-severity-lt-high", "severity < 'high'")

    # Should match: info, low, warning
    info_alert = create_alert(severity=AlertSeverity.INFO, fingerprint="fp-info")
    low_alert = create_alert(severity=AlertSeverity.LOW, fingerprint="fp-low")
    warning_alert = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp-warning")

    # Should NOT match: high, critical
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    critical_alert = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp-critical")

    # Test matching severities
    for alert in [info_alert, low_alert, warning_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1

    # Test non-matching severities  
    for alert in [high_alert, critical_alert]:
        workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])
        assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_complex_severity_expressions(
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


def test_case_insensitive_severity_comparisons(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test that severity comparisons are case-insensitive after preprocessing"""
    workflow = create_workflow("test-severity-case", "severity > 'INFO'")

    # Should match despite case difference in CEL expression
    high_alert = create_alert(severity=AlertSeverity.HIGH, fingerprint="fp-high")
    
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [high_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    

def test_severity_preprocessing_cel_utils_integration(
    db_session, workflow_manager, create_workflow, create_alert
):
    """
    Test that the cel_utils.preprocess_cel_expression function is properly integrated
    into the workflow manager to fix the lexicographic comparison bug
    """
    
    # This test specifically validates that lexicographic issues are resolved
    # Before fix: 'high' < 'info' lexicographically (h comes before i in alphabet)
    # After fix: high (4) > info (2) numerically
    
    workflow = create_workflow(
        "test-preprocessing-integration", 
        "severity > 'info'"
    )

    # Create a 'high' severity alert - this is the key test case
    # that would fail with lexicographic comparison but should pass with numeric
    high_alert = create_alert(
        severity=AlertSeverity.HIGH,
        source=["test"], 
        fingerprint="fp-high-severity"
    )

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [high_alert])
    
    # This assertion would fail before the fix, but should pass after
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1, \
        "HIGH severity alert should match 'severity > info' expression after preprocessing fix"
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id