from pathlib import Path
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from keep.api.routes.workflows import get_event_from_body
from keep.parser.parser import Parser
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.incident import IncidentDto
from keep.api.models.db.incident import IncidentSeverity, IncidentStatus

# Assuming WorkflowParser is the class containing the get_workflow_from_dict method
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.workflowmanager.workflowscheduler import WorkflowScheduler
from keep.workflowmanager.workflowstore import WorkflowStore

path_to_test_resources = Path(__file__).parent / "workflows"


def test_get_workflow_from_dict():
    mock_parser = Mock(spec=Parser)
    mock_workflow = Mock(spec=Workflow, workflow_id="workflow1")
    mock_parser.parse.return_value = [mock_workflow]
    workflow_store = WorkflowStore()
    workflow_store.parser = mock_parser

    tenant_id = "test_tenant"
    workflow_path = str(path_to_test_resources / "db_disk_space_for_testing.yml")
    workflow_dict = workflow_store._parse_workflow_to_dict(workflow_path=workflow_path)
    result = workflow_store.get_workflow_from_dict(
        tenant_id=tenant_id, workflow_dict=workflow_dict
    )
    mock_parser.parse.assert_called_once_with(tenant_id, workflow_dict)
    assert result.workflow_id == "workflow1"


def test_get_workflow_from_dict_raises_exception():
    mock_parser = Mock(spec=Parser)
    mock_parser.parse.return_value = []
    workflow_store = WorkflowStore()
    workflow_store.parser = mock_parser

    tenant_id = "test_tenant"

    workflow_path = str(path_to_test_resources / "db_disk_space_for_testing.yml")
    workflow_dict = workflow_store._parse_workflow_to_dict(workflow_path=workflow_path)

    with pytest.raises(HTTPException) as exc_info:
        workflow_store.get_workflow_from_dict(
            tenant_id=tenant_id, workflow_dict=workflow_dict
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Unable to parse workflow from dict"
    mock_parser.parse.assert_called_once_with(tenant_id, workflow_dict)


def test_get_workflow_results():

    mock_action1 = Mock(name="action1")
    mock_action1.name = "action1"
    mock_action1.provider.results = {"result": "value1"}

    mock_action2 = Mock(name="action2")
    mock_action2.name = "action2"
    mock_action2.provider.results = {"result": "value2"}

    mock_step1 = Mock(name="step1")
    mock_step1.name = "step1"
    mock_step1.provider.results = {"result": "value3"}

    mock_step2 = Mock(name="step2")
    mock_step2.name = "step2"
    mock_step2.provider.results = {"result": "value4"}

    mock_workflow = Mock(spec=Workflow)
    mock_workflow.workflow_actions = [mock_action1, mock_action2]
    mock_workflow.workflow_steps = [mock_step1, mock_step2]

    workflow_manager = WorkflowManager()
    result = workflow_manager._get_workflow_results(mock_workflow)

    expected_result = {
        "action1": {"result": "value1"},
        "action2": {"result": "value2"},
        "step1": {"result": "value3"},
        "step2": {"result": "value4"},
    }

    assert result == expected_result


def test_handle_manual_event_workflow():
    mock_workflow = Mock(spec=Workflow)
    mock_workflow.workflow_id = "workflow1"
    mock_workflow.workflow_revision = 1
    mock_workflow_manager = Mock()

    mock_logger = Mock()

    workflow_scheduler = WorkflowScheduler(workflow_manager=mock_workflow_manager)
    workflow_scheduler.logger = mock_logger
    workflow_scheduler.workflow_manager = mock_workflow_manager

    workflow_scheduler._get_unique_execution_number = Mock(return_value=123)
    workflow_scheduler._finish_workflow_execution = Mock()

    # Mock create_workflow_execution
    with patch(
        "keep.workflowmanager.workflowscheduler.create_workflow_execution"
    ) as mock_create_execution:
        mock_create_execution.return_value = "test_execution_id"

        tenant_id = "test_tenant"
        triggered_by_user = "test_user"

        event, _ = get_event_from_body(
            body={"body": {"fingerprint": "manual-run"}}, tenant_id=tenant_id
        )

        workflow_execution_id = workflow_scheduler.handle_manual_event_workflow(
            workflow_id=mock_workflow.workflow_id,
            workflow_revision=mock_workflow.workflow_revision,
            tenant_id=tenant_id,
            triggered_by_user=triggered_by_user,
            event=event,
        )

        assert workflow_execution_id == "test_execution_id"
        assert len(workflow_scheduler.workflows_to_run) == 1
        workflow_run = workflow_scheduler.workflows_to_run[0]
        assert workflow_run["workflow_execution_id"] == "test_execution_id"
        assert workflow_run["workflow_id"] == mock_workflow.workflow_id
        assert workflow_run["tenant_id"] == tenant_id
        assert workflow_run["triggered_by_user"] == triggered_by_user
        assert workflow_run["event"] == event


def test_handle_manual_event_workflow_test_run():
    mock_workflow = Mock(spec=Workflow)
    mock_workflow.workflow_id = "workflow1"
    mock_workflow.workflow_revision = 1

    mock_workflow_manager = Mock()

    mock_logger = Mock()

    workflow_scheduler = WorkflowScheduler(workflow_manager=mock_workflow_manager)
    workflow_scheduler.logger = mock_logger
    workflow_scheduler.workflow_manager = mock_workflow_manager

    workflow_scheduler._get_unique_execution_number = Mock(return_value=123)
    workflow_scheduler._finish_workflow_execution = Mock()

    # Mock create_workflow_execution
    with patch(
        "keep.workflowmanager.workflowscheduler.create_workflow_execution"
    ) as mock_create_execution:
        mock_create_execution.return_value = "test_execution_id"

        tenant_id = "test_tenant"
        triggered_by_user = "test_user"

        event, _ = get_event_from_body(
            body={"body": {"fingerprint": "manual-run"}}, tenant_id=tenant_id
        )

        workflow_execution_id = workflow_scheduler.handle_manual_event_workflow(
            workflow_id=mock_workflow.workflow_id,
            workflow_revision=mock_workflow.workflow_revision,
            workflow=mock_workflow,
            tenant_id=tenant_id,
            triggered_by_user=triggered_by_user,
            event=event,
            test_run=True,
        )

        assert workflow_execution_id == "test_execution_id"
        assert len(workflow_scheduler.workflows_to_run) == 1
        assert (
            workflow_scheduler.workflows_to_run[0]["workflow_execution_id"]
            == "test_execution_id"
        )
        assert workflow_scheduler.workflows_to_run[0]["test_run"] == True
        assert workflow_scheduler.workflows_to_run[0]["workflow"] == mock_workflow

def test_insert_incident_alert_association_changed_adds_linked_alerts():
    """Test that linked_alerts key is present when workflow trigger is alert_association_changed."""

    # Create mock alerts that would be associated with the incident
    mock_alert_1 = AlertDto(
        id="alert-1",
        name="Test Alert 1",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.HIGH,
        lastReceived="2025-01-30T10:00:00Z",
        description="Test alert 1 description\nThis is a multiline description\nWith multiple lines of content\nTo test the split behavior"
    )

    mock_alert_2 = AlertDto(
        id="alert-2",
        name="Test Alert 2",
        status=AlertStatus.RESOLVED,
        severity=AlertSeverity.CRITICAL,
        lastReceived="2025-01-30T11:00:00Z",
        description="Test alert 2 description"
    )

    # Create incident DTO with mock alerts
    incident_dto = IncidentDto(
        id=uuid.uuid4(),
        user_generated_name="Test Incident",
        alerts_count=2,
        alert_sources=["prometheus", "grafana"],
        services=["web-service"],
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.FIRING,
        is_predicted=False,
        is_candidate=False,
        creation_time=datetime.utcnow()
    )

    # Mock the alerts property to return our test alerts
    incident_dto._alerts = [mock_alert_1, mock_alert_2]

    # Create a mock workflow with alert_association_changed trigger
    mock_workflow = Mock(spec=Workflow)
    mock_workflow.workflow_triggers = [
        {
            "type": "incident",
            "events": ["alert_association_changed"]
        }
    ]

    # Create mock workflow model
    mock_workflow_model = Mock()
    mock_workflow_model.id = "test-workflow-id"
    mock_workflow_model.name = "test-workflow"
    mock_workflow_model.tenant_id = "test-tenant"
    mock_workflow_model.is_disabled = False

    # Create WorkflowManager and mock dependencies
    workflow_manager = WorkflowManager()

    with patch.object(workflow_manager.workflow_store, 'get_all_workflows') as mock_get_workflows, \
         patch.object(workflow_manager, '_get_workflow_from_store') as mock_get_workflow, \
         patch('keep.workflowmanager.workflowmanager.get_enrichment') as mock_get_enrichment:

        # Set up mocks
        mock_get_workflows.return_value = [mock_workflow_model]
        mock_get_workflow.return_value = mock_workflow
        mock_get_enrichment.return_value = None

        # Mock the scheduler
        workflow_manager.scheduler = Mock()
        workflow_manager.scheduler.lock = Mock()
        workflow_manager.scheduler.lock.__enter__ = Mock(return_value=None)
        workflow_manager.scheduler.lock.__exit__ = Mock(return_value=None)
        workflow_manager.scheduler.workflows_to_run = []

        # Call insert_incident with alert_association_changed trigger
        workflow_manager.insert_incident("test-tenant", incident_dto, "alert_association_changed")

        # Verify workflow was added to run
        assert len(workflow_manager.scheduler.workflows_to_run) == 1

        # Get the workflow execution event
        workflow_execution = workflow_manager.scheduler.workflows_to_run[0]
        executed_incident = workflow_execution["event"]

        # Verify that linked_alerts attribute was added to the incident
        assert hasattr(executed_incident, 'linked_alerts'), "linked_alerts attribute should be present"

        # Verify the content of linked_alerts
        linked_alerts = executed_incident.linked_alerts
        assert isinstance(linked_alerts, list), "linked_alerts should be a list"
        assert len(linked_alerts) == 2, "Should have 2 linked alerts"

        # Verify the format of linked alerts entries
        expected_alert_1 = "Firing 2025-01-30T10:00:00.000Z [high] Test alert 1 description"
        expected_alert_2 = "Resolved 2025-01-30T11:00:00.000Z [critical] Test alert 2 description"

        assert expected_alert_1 in linked_alerts, f"Expected '{expected_alert_1}' in linked_alerts"
        assert expected_alert_2 in linked_alerts, f"Expected '{expected_alert_2}' in linked_alerts"
