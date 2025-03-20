from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from keep.api.routes.workflows import get_event_from_body
from keep.parser.parser import Parser

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
        tenant_id=tenant_id, workflow=workflow_dict
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
            tenant_id=tenant_id, workflow=workflow_dict
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

    mock_workflow_manager = Mock()

    mock_logger = Mock()

    workflow_scheduler = WorkflowScheduler(workflow_manager=mock_workflow_manager)
    workflow_scheduler.logger = mock_logger
    workflow_scheduler.workflow_manager = mock_workflow_manager

    workflow_scheduler._get_unique_execution_number = Mock(return_value=123)
    workflow_scheduler._finish_workflow_execution = Mock()

    # Mock create_workflow_execution
    with patch('keep.workflowmanager.workflowscheduler.create_workflow_execution') as mock_create_execution:
        mock_create_execution.return_value = "test_execution_id"

        tenant_id = "test_tenant"
        triggered_by_user = "test_user"

        event = get_event_from_body(body={"body": {"fingerprint": "manual-run"}}, tenant_id=tenant_id)

        workflow_execution_id = workflow_scheduler.handle_manual_event_workflow(
            workflow_id=mock_workflow.workflow_id,
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

    mock_workflow_manager = Mock()

    mock_logger = Mock()

    workflow_scheduler = WorkflowScheduler(workflow_manager=mock_workflow_manager)
    workflow_scheduler.logger = mock_logger
    workflow_scheduler.workflow_manager = mock_workflow_manager

    workflow_scheduler._get_unique_execution_number = Mock(return_value=123)
    workflow_scheduler._finish_workflow_execution = Mock()

    # Mock create_workflow_execution
    with patch('keep.workflowmanager.workflowscheduler.create_workflow_execution') as mock_create_execution:
        mock_create_execution.return_value = "test_execution_id"

        tenant_id = "test_tenant"
        triggered_by_user = "test_user"

        event = get_event_from_body(body={"body": {"fingerprint": "manual-run"}}, tenant_id=tenant_id)

        workflow_execution_id = workflow_scheduler.handle_manual_event_workflow(
            workflow_id=mock_workflow.workflow_id,
            workflow=mock_workflow,
            tenant_id=tenant_id,
            triggered_by_user=triggered_by_user,
            event=event,
            test_run=True,
        )

        assert workflow_execution_id == "test_execution_id"
        assert len(workflow_scheduler.workflows_to_run) == 1
        assert workflow_scheduler.workflows_to_run[0]["workflow_execution_id"] == "test_execution_id"
        assert workflow_scheduler.workflows_to_run[0]["test_run"] == True
        assert workflow_scheduler.workflows_to_run[0]["workflow"] == mock_workflow
