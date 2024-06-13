import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

# Assuming WorkflowParser is the class containing the get_workflow_from_dict method
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowstore import WorkflowStore
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.parser.parser import Parser
from pathlib import Path

path_to_test_resources = Path(__file__).parent / "workflows"


def test_get_workflow_from_dict():
    mock_parser = Mock(spec=Parser)
    mock_workflow = Mock(spec=Workflow, id="workflow1")
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
    assert result.id == "workflow1"


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

    # Create a mock Workflow object with actions and steps
    mock_workflow = Mock(spec=Workflow)
    mock_workflow.workflow_actions = [mock_action1, mock_action2]
    mock_workflow.workflow_steps = [mock_step1, mock_step2]

    workflow_manager = WorkflowManager()
    # Call the method under test
    result = workflow_manager._get_workflow_results(mock_workflow)

    # Define the expected result
    expected_result = {
        "action1": {"result": "value1"},
        "action2": {"result": "value2"},
        "step1": {"result": "value3"},
        "step2": {"result": "value4"},
    }

    # Assert that the result is as expected
    assert result == expected_result
