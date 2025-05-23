import datetime

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.workflow import Workflow
from keep.workflowmanager.workflowmanager import WorkflowManager


@pytest.fixture
def workflow_manager():
    manager = WorkflowManager.get_instance()
    return manager


@pytest.fixture
def create_workflow(db_session):
    """Fixture to create a workflow with a specific CEL expression"""

    def _create_workflow(workflow_id, cel_expression):
        workflow_definition = f"""workflow:
  id: {workflow_id}
  description: Test CEL expressions
  triggers:
    - type: alert
      cel: "{cel_expression}"
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


def test_handling_special_characters(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test handling of fields with special characters"""
    # Create a workflow that checks fields with special characters
    workflow = create_workflow(
        "test-special-chars", '`@timestamp` > "2023-01-01T00:00:00Z"'
    )

    # Create an alert that should match
    alert = create_alert(**{"@timestamp": "2023-05-01T00:00:00Z"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create an alert that should not match
    alert_not_matching = create_alert(**{"@timestamp": "2022-05-01T00:00:00Z"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_not_matching])

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


def test_only_on_change_functionality(
    db_session, workflow_manager, create_workflow, create_alert, mocker
):
    """Test the only_on_change functionality in CEL triggers"""
    # Mock the get_previous_alert_by_fingerprint function
    mock_previous_alert = mocker.patch(
        "keep.workflowmanager.workflowmanager.get_previous_alert_by_fingerprint"
    )

    # Create a workflow with only_on_change for severity
    workflow_def = """workflow:
  id: test-only-on-change
  description: Test only_on_change functionality
  triggers:
    - type: alert
      cel: 'severity == "critical"'
      only_on_change: ["message"]
  actions:
    - name: test-action
      provider:
        type: console
        with:
          message: "Alert changed"
"""

    workflow = Workflow(
        id="test-only-on-change",
        name="test-only-on-change",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test only_on_change functionality",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_def,
    )
    db_session.add(workflow)
    db_session.commit()

    # Set up the mock to return a previous alert with the same message
    mock_previous_alert.return_value = {"event": {"message": "Previous message"}}

    # Create an alert with a different message
    alert = create_alert(severity=AlertSeverity.CRITICAL, message="New message")

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run due to message change
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Now set up the mock to return a previous alert with the same message
    mock_previous_alert.return_value = {"event": {"message": "New message"}}

    # Create another alert with the same message
    alert_same_message = create_alert(
        severity=AlertSeverity.CRITICAL,
        message="New message",
        fingerprint="different-fingerprint",
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_same_message])

    # Check if no new workflow was scheduled to run since the message didn't change
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_severity_changed_functionality(
    db_session, workflow_manager, create_workflow, create_alert, mocker
):
    """Test the severity_changed functionality in CEL triggers"""
    # Mock the get_previous_alert_by_fingerprint function
    mock_previous_alert = mocker.patch(
        "keep.workflowmanager.workflowmanager.get_previous_alert_by_fingerprint"
    )

    # Create a workflow with severity_changed flag
    workflow_def = """workflow:
  id: test-severity-changed
  description: Test severity_changed functionality
  triggers:
    - type: alert
      cel: 'source.contains("test-source")'
      severity_changed: true
  actions:
    - name: test-action
      provider:
        type: console
        with:
          message: "Severity changed"
"""

    workflow = Workflow(
        id="test-severity-changed",
        name="test-severity-changed",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test severity_changed functionality",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_def,
    )
    db_session.add(workflow)
    db_session.commit()

    # Set up the mock to return a previous alert with a different severity
    mock_previous_alert.return_value = {"event": {"severity": "warning"}}

    # Create an alert with a different severity
    alert = create_alert(
        severity=AlertSeverity.CRITICAL,
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run due to severity change
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Check if the severity_changed and related fields were added to the event
    event = workflow_manager.scheduler.workflows_to_run[-1]["event"]
    assert event.severity_changed is True
    assert event.previous_severity == "warning"
    assert event.severity_change == "increased"  # Changed from warning to critical

    # Now set up the mock to return a previous alert with the same severity
    mock_previous_alert.return_value = {"event": {"severity": "critical"}}

    # Create another alert with the same severity
    alert_same_severity = create_alert(
        severity=AlertSeverity.CRITICAL, fingerprint="different-fingerprint"
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_same_severity])

    # Check if no new workflow was scheduled to run since the severity didn't change
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before


def test_conditional_cel_with_labels(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test conditional CEL expressions with labels"""
    # Create a workflow with a conditional expression using labels
    workflow = create_workflow(
        "test-conditional-labels",
        'has(labels.environment) ? labels.environment == "production" : false',
    )

    # Create an alert that should match
    alert = create_alert(labels={"environment": "production"})

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow.id

    # Create alerts that should not match
    alert_wrong_value = create_alert(labels={"environment": "staging"})
    alert_missing_label = create_alert(labels={})

    # Insert the alerts into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_wrong_value])
    assert len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before

    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert_missing_label])
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


def test_special_characters_in_cel(
    db_session, workflow_manager, create_workflow, create_alert
):
    """Test handling of special characters in CEL expressions"""
    # Create workflows with special characters in CEL
    workflow1 = create_workflow(
        "test-special-chars-1", '`@timestamp` != "" && `#special` == "value"'
    )

    # Create an alert with special character fields
    alert = create_alert(
        **{
            "@timestamp": "2023-05-01T00:00:00Z",
            "#special": "value",
            "!important": True,
        }
    )

    # Insert the alert into the workflow manager
    workflows_to_run_before = len(workflow_manager.scheduler.workflows_to_run)
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [alert])

    # Check if the workflow was scheduled to run
    assert (
        len(workflow_manager.scheduler.workflows_to_run) == workflows_to_run_before + 1
    )
    assert (
        workflow_manager.scheduler.workflows_to_run[-1]["workflow_id"] == workflow1.id
    )
