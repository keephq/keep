import datetime

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.workflow import Workflow

# from keep.workflowmanager.workflowmanager import WorkflowManager
from tests.fixtures.workflow_manager import workflow_manager  # noqa


@pytest.fixture
def create_workflow(db_session):
    """Fixture to create a workflow with a specific CEL expression"""

    def _create_workflow(workflow_id, cel_expression):
        workflow_definition = f"""workflow:
  id: {workflow_id}
  description: Test CEL expressions
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
            description="Test CEL expressions",
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
            "source": ["test-source"],
            "name": "test-alert",
            "status": AlertStatus.FIRING,
            "severity": AlertSeverity.CRITICAL,
            "lastReceived": datetime.datetime.now().isoformat(),
            "fingerprint": "test-fingerprint",
        }
        alert_data.update(properties)
        return AlertDto(**alert_data)

    return _create_alert


def test_simple_equality_expression(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test simple equality expression in CEL"""
    # Create a workflow with a simple equality expression
    workflow = create_workflow("test-simple-equality", 'name == "test-alert"')

    # Create an alert that should match
    alert = create_alert(name="test-alert")

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(name="different-alert")

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_simple_source_equality_expression(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test simple equality expression in CEL"""
    # Create a workflow with a simple equality expression
    workflow = create_workflow("test-simple-equality", 'source == "datadog"')

    # Create an alert that should match
    alert = create_alert(name="test-alert", source=["datadog"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(name="different-alert", source=["sentry"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_source_contains_expression(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test source.contains() expression in CEL"""
    # Create a workflow with a source.contains expression
    workflow = create_workflow("test-source-contains", 'source.contains("grafana")')

    # Create an alert that should match
    alert = create_alert(source=["grafana", "prometheus"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(source=["sentry", "datadog"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_nested_property_access(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test accessing nested properties in CEL"""
    # Create a workflow that checks a nested property
    workflow = create_workflow(
        "test-nested-property", 'labels.environment == "production"'
    )

    # Create an alert that should match
    alert = create_alert(labels={"environment": "production", "service": "api"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(
        labels={"environment": "staging", "service": "api"}
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_deeply_nested_property_access(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test accessing deeply nested properties in CEL"""
    # Create a workflow that checks a deeply nested property
    workflow = create_workflow(
        "test-deeply-nested-property", 'labels.metadata.region == "us-east"'
    )

    # Create an alert that should match
    alert = create_alert(
        labels={
            "environment": "production",
            "metadata": {"region": "us-east", "datacenter": "dc1"},
        }
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(
        labels={
            "environment": "production",
            "metadata": {"region": "eu-west", "datacenter": "dc2"},
        }
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_complex_boolean_expression(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test complex boolean expressions in CEL"""
    # Create a workflow with a complex boolean expression
    create_workflow(
        "test-complex-boolean",
        '(severity == "critical" && source.contains("grafana")) || (name.contains("urgent") && labels.priority == "high")',
    )

    # Create alerts that should match different conditions
    alert1 = create_alert(
        severity=AlertSeverity.CRITICAL, source=["grafana", "prometheus"]
    )

    alert2 = create_alert(
        name="urgent-database-issue",
        severity=AlertSeverity.WARNING,
        source=["datadog"],
        labels={"priority": "high"},
    )

    # Create an alert that should not match
    alert_not_matching = create_alert(
        severity=AlertSeverity.WARNING,
        source=["datadog"],
        labels={"priority": "medium"},
    )

    # Insert alerts and verify matching
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert1])
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert2])
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_list_operations(db_session, workflow_manager, create_workflow, create_alert):
    """Test list operations in CEL"""
    # Create a workflow that checks if a tag is in a list
    workflow = create_workflow("test-list-operations", 'tags.contains("database")')

    # Create an alert that should match
    alert = create_alert(tags=["database", "mysql", "production"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(tags=["api", "web", "production"])

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_string_operations(db_session, workflow_manager, create_workflow, create_alert):
    """Test string operations in CEL"""
    # Create a workflow that checks string operations
    workflow = create_workflow(
        "test-string-operations",
        'name.startsWith("db-") && description.contains("connection")',
    )

    # Create an alert that should match
    alert = create_alert(
        name="db-postgres-alert", description="Database connection timeout"
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create alerts that should not match
    alert_not_matching1 = create_alert(
        name="api-service-alert", description="Database connection timeout"
    )

    alert_not_matching2 = create_alert(
        name="db-postgres-alert", description="High CPU usage"
    )

    # Insert the alerts into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching1])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching2])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_numeric_comparisons(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test numeric comparisons in CEL"""
    # Create a workflow with numeric comparisons
    workflow = create_workflow(
        "test-numeric-comparisons",
        "metrics.cpu_usage > 90 && metrics.memory_usage >= 80",
    )

    # Create an alert that should match
    alert = create_alert(
        metrics={"cpu_usage": 95, "memory_usage": 85, "disk_usage": 70}
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create alerts that should not match
    alert_not_matching1 = create_alert(
        metrics={"cpu_usage": 85, "memory_usage": 85, "disk_usage": 70}
    )

    alert_not_matching2 = create_alert(
        metrics={"cpu_usage": 95, "memory_usage": 75, "disk_usage": 70}
    )

    # Insert the alerts into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching1])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching2])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_handling_missing_fields(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test how CEL handles missing fields"""
    # Create a workflow that checks for an optional field
    workflow = create_workflow(
        "test-missing-fields", 'has(labels.priority) && labels.priority == "high"'
    )

    # Create an alert that should match
    alert = create_alert(labels={"priority": "high", "service": "api"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert without the optional field
    alert_missing_field = create_alert(labels={"service": "api"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_missing_field])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_multiple_workflows_matching(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test that multiple workflows can match the same alert"""
    # Create two workflows with different expressions
    workflow1 = create_workflow("test-multi-match-1", 'severity == "critical"')
    workflow2 = create_workflow("test-multi-match-2", 'source.contains("grafana")')

    # Create an alert that should match both workflows
    alert = create_alert(
        severity=AlertSeverity.CRITICAL, source=["grafana", "prometheus"]
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if both workflows were scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 2
    )

    # Verify both workflow IDs are in the list
    workflow_ids = [
        item["workflow_id"] for item in workflow_manager.scheduler.workflows_to_run[-2:]
    ]
    assert workflow1.id in workflow_ids
    assert workflow2.id in workflow_ids


def test_regex_in_cel(db_session, workflow_manager, create_workflow, create_alert):
    """Test regex-like matching in CEL"""
    # Create a workflow with string matching that simulates regex
    workflow = create_workflow("test-regex-like", 'name.matches("error-[0-9]+")')

    # Create an alert that should match
    alert = create_alert(name="error-123")

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(name="warning-123")

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

    # Check if no new workflow was scheduled to run
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_multiple_alerts_batch(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test processing multiple alerts in a batch"""
    # Create a workflow that should match some alerts
    create_workflow("test-multiple-alerts", 'severity == "critical"')

    # Create a batch of alerts with different severities
    alert1 = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp1")
    alert2 = create_alert(severity=AlertSeverity.WARNING, fingerprint="fp2")
    alert3 = create_alert(severity=AlertSeverity.CRITICAL, fingerprint="fp3")

    # Insert all alerts in a batch
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert1, alert2, alert3])

    # Check if the workflow was scheduled to run for the critical alerts only
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 2
    )

    # Verify the workflow was scheduled for the correct alerts
    workflow_alerts = [
        item["event"].fingerprint
        for item in workflow_manager.scheduler.workflows_to_run[-2:]
    ]
    assert "fp1" in workflow_alerts
    assert "fp3" in workflow_alerts
    assert "fp2" not in workflow_alerts


def test_cel_expression_with_null_field_bug(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test bug where CEL expressions with null field checks don't trigger workflows"""
    # Create a workflow that mimics the user's issue:
    # Should trigger when source matches, status is firing, and slackTimestamp is null
    workflow = create_workflow(
        "test-null-field-bug",
        '(source == "GitlabServices" && status == "firing" && !has(slackTimestamp))',
    )

    # Create an alert that should match the CEL expression
    # This represents the GitLab Services alert that should trigger the workflow
    alert_matching = create_alert(
        source=["GitlabServices"],  # Note: source is a list in the AlertDto
        status=AlertStatus.FIRING,
        # slackTimestamp should be null/missing to match the CEL expression
        # We don't set it, so it should be None/null
        buildName="test-build-123",
        branchRef="main",
        projectName="test-project",
        userRef="john.doe",
        buildUrl="https://gitlab.example.com/job/123",
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_matching])

    # Check if the workflow was scheduled to run
    # This assertion should pass if the bug is fixed
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    ), f"Expected workflow to be triggered, but got {len(workflow_manager.scheduler.workflows_to_run) - workflows_to_run_before} new workflows"

    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Test case where slackTimestamp is not null - should NOT match
    alert_with_timestamp = create_alert(
        source=["GitlabServices"],
        status=AlertStatus.FIRING,
        slackTimestamp="1234567890.123456",  # Has a timestamp, so should not match
        buildName="test-build-456",
    )

    # Insert the alert with timestamp
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_with_timestamp])

    # Should not trigger workflow since slackTimestamp is not null
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    # Test case where source doesn't match - should NOT match
    alert_wrong_source = create_alert(
        source=["DifferentService"],
        status=AlertStatus.FIRING,
        # slackTimestamp is null/missing
        buildName="test-build-789",
    )

    # Insert the alert with wrong source
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_wrong_source])

    # Should not trigger workflow since source doesn't match
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    # Test case where status is not firing - should NOT match
    alert_wrong_status = create_alert(
        source=["GitlabServices"],
        status=AlertStatus.RESOLVED,  # Not firing
        # slackTimestamp is null/missing
        buildName="test-build-101",
    )

    # Insert the alert with wrong status
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_wrong_status])

    # Should not trigger workflow since status is not firing
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before
