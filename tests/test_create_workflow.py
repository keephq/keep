import uuid
import builtins
import json
import time
from pathlib import Path
import pytest
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.workflowmanager.workflowstore import WorkflowStore
from unittest.mock import MagicMock, patch
from fastapi import HTTPException



@pytest.fixture
def mock_uuid():
    index = 0

    def generate_uuid():
        nonlocal index
        index += 1
        return "my-fixed-uuid" + str(index)

    with patch('uuid.uuid4', generate_uuid):
        yield




#Here we can add deprecated payloads also to test the workflow creation.
def get_sample_mock_workflow(name=None, id=None, provisioned=False):
    sample = {
        "description": "test workflow",
        "interval": 0,
        "triggers": [
            {
                "type": "mock",
                "filters": [
                    {
                        "key": "name",
                        "value": "test alert"
                    }
                ]
            }
        ],
        "actions": [
            {
                "name": "test action",
                "provider": {
                    "type": "mock"
                }
            }
        ]
    }

    if name : 
        sample["name"] = name
    if id :
        sample["id"] = id   

    if provisioned :
        sample["provisioned"] = provisioned     

    return sample    


def test_create_workflow_check(db_session, mock_uuid):
    workflow_store = WorkflowStore()
    # create mock workflow
    mock_workflow = get_sample_mock_workflow(name="test_name")
    result = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow)
    assert result.id == "my-fixed-uuid1"
    assert result.name == "test_name"



def test_create_workflow_where_id_exists_in_db(db_session, mock_uuid):
    workflow_store = WorkflowStore()
    # create mock workflow
    mock_workflow1 = get_sample_mock_workflow(name="test_workflow")
    result1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1)
    assert result1.id == "my-fixed-uuid1"
    assert result1.name == "test_workflow"
    #It is exact copy of above mock workflow. this should workflow should have unique id
    mock_workflow1_1 = get_sample_mock_workflow(name="test_workflow")
    result_1_1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1_1)
    assert result_1_1.id == "my-fixed-uuid2"
    assert result_1_1.name == "test_workflow"

    mock_workflow2 = get_sample_mock_workflow(name="test workflow 2")
    result2 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow2)
    assert result2.id == "my-fixed-uuid3"
    assert result2.name == "test workflow 2"

    #If a valid workflow UUID is provided and it exists in the database, the workflow data will be updated
    mock_workflow3 = get_sample_mock_workflow(name="test workflow 1", id="my-fixed-uuid1")
    result3 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow3)
    assert result3.id == "my-fixed-uuid1"
    assert result3.name == "test workflow 1"


def test_create_workflow_when_there_is_no_name(db_session, mock_uuid):
    workflow_store = WorkflowStore()
    # create mock workflow
    mock_workflow1 = get_sample_mock_workflow("test_workflow")
    result1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1)
    assert result1.id == "my-fixed-uuid1"
    assert result1.name == "test_workflow"
    #It is exact copy of above mock workflow. this should workflow should have unique id
    mock_workflow1_1 = get_sample_mock_workflow()
    with pytest.raises(HTTPException) as workflow_info:
        workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1_1)

    assert workflow_info.value.status_code == 400
    assert workflow_info.value.detail == "Workflow name is required"

    #If a valid workflow UUID is provided and it exists in the database, the workflow data will be updated
    mock_workflow3 = get_sample_mock_workflow(name="test workflow 1", id="my-fixed-uuid1")
    result3 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow3)
    assert result3.id == "my-fixed-uuid1"
    assert result3.name == "test workflow 1"


def test_create_workflow_when_there_is_id_and_name(db_session, mock_uuid):
    #In the case. If a workflow with the given ID exists, update it. Otherwise, create a new workflow.
    workflow_store = WorkflowStore()
    # create mock workflow
    mock_workflow1 = get_sample_mock_workflow(name="test workflow", id="test-1") # this id does not exist in db. so it will create new workflow with new UUID
    result1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1)
    assert result1.id == "my-fixed-uuid1"
    assert result1.name == "test workflow"
    #It is exact copy of above mock workflow. this should workflow should have unique id
    mock_workflow1_1 = get_sample_mock_workflow(name="test workflow", id="test-1") #this id does not exist in db.  so it will create new workflow with new UUID
    result_1_1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1_1)
    assert result_1_1.id == "my-fixed-uuid2"
    assert result_1_1.name == "test workflow"

    #If a valid workflow UUID is provided and it exists in the database, the workflow data will be updated
    mock_workflow3 = get_sample_mock_workflow(name="test workflow 1", id="my-fixed-uuid1")
    result3 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow3)
    assert result3.id == "my-fixed-uuid1"
    assert result3.name == "test workflow 1"


def test_create_workflow_when_there_is_id_and_no_name(db_session, mock_uuid):
    workflow_store = WorkflowStore()
    # create mock workflow
    #this is only possible via cli or upload only
    mock_workflow1 = get_sample_mock_workflow(id="test-1") # this id does not exist in db. so it will create new workflow with new UUID
    result1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1)
    assert result1.id == "my-fixed-uuid1"
    assert result1.name == "test-1"
    #It is exact copy of above mock workflow. this should workflow should have unique id
    mock_workflow1_1 = get_sample_mock_workflow(id="test-1") #this id does not exist in db.  so it will create new workflow with new UUID
    result_1_1 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow1_1)
    assert result_1_1.id == "my-fixed-uuid2"
    assert result_1_1.name == "test-1"

    #If a valid workflow UUID is provided and it exists in the database, the workflow data will be updated
    mock_workflow3 = get_sample_mock_workflow(id="my-fixed-uuid1", name="test workflow 1")
    result3 = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow3)
    assert result3.id == "my-fixed-uuid1"
    assert result3.name == "test workflow 1"


def test_create_worfklow_already_provisioned_workflow_should_not_update(db_session, mock_uuid):
    workflow_store = WorkflowStore()
    # create mock workflow
    mock_workflow = get_sample_mock_workflow(name="test_name", provisioned=True)   
    result = workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow)
    assert result.id == "my-fixed-uuid1"
    assert result.name == "test_name"
    assert result.provisioned == True

    mock_workflow_1 = get_sample_mock_workflow(name="test_name1", id="my-fixed-uuid1")
    
    with pytest.raises(HTTPException) as workflow_info:
        workflow_store.create_workflow(tenant_id=SINGLE_TENANT_UUID, created_by="test", workflow=mock_workflow_1)

    assert workflow_info.value.detail == "Cannot update a provisioned workflow"