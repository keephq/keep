from keep.api.models.db.workflow import (
    WorkflowExecution,
    WorkflowExecutionLog,
    Workflow,
)
from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from keep.workflowmanager.dal.sql.mappers import (
    workflow_from_db_to_dto,
    workflow_execution_from_db_to_dto,
    workflow_execution_log_from_db_to_dto,
    workflow_execution_from_dto_to_db_partial,
)


def test_mapping_workflow_db_to_dto():
    workflow_db = Workflow(
        id="1",
        tenant_id="tenant_1",
        name="Test Workflow",
        description="A test workflow",
        created_by="user_1",
        creation_time=1234567890,
        interval=60,
        workflow_raw="{}",
        is_deleted=False,
        is_disabled=False,
        revision=1,
        last_updated=1234567890,
        provisioned=False,
        provisioned_file="wokrflow.yml",
        is_test=False,
    )
    workflow_dto = workflow_from_db_to_dto(workflow_db)
    assert isinstance(workflow_dto, WorkflowDalModel)
    assert workflow_dto.id == workflow_db.id
    assert workflow_dto.tenant_id == workflow_db.tenant_id
    assert workflow_dto.name == workflow_db.name
    assert workflow_dto.description == workflow_db.description
    assert workflow_dto.created_by == workflow_db.created_by
    assert workflow_dto.creation_time == workflow_db.creation_time
    assert workflow_dto.interval == workflow_db.interval
    assert workflow_dto.workflow_raw == workflow_db.workflow_raw
    assert workflow_dto.is_deleted == workflow_db.is_deleted
    assert workflow_dto.is_disabled == workflow_db.is_disabled
    assert workflow_dto.revision == workflow_db.revision
    assert workflow_dto.last_updated == workflow_db.last_updated
    assert workflow_dto.provisioned == workflow_db.provisioned
    assert workflow_dto.provisioned_file == workflow_db.provisioned_file
    assert workflow_dto.is_test == workflow_db.is_test


def test_mapping_workflow_execution_db_to_dto():
    workflow_execution_db = WorkflowExecution(
        id="1",
        workflow_id="workflow_1",
        workflow_revision=1,
        tenant_id="tenant_1",
        started=1234567890,
        triggered_by="user_1",
        status="running",
        is_running=True,
        timeslot=1234567890,
        execution_number=1,
        error="Error running workflow",
        workflow_to_alert_execution=None,
        workflow_to_incident_execution=None,
        results={
            "result_key": "result_value",
            "another_key": "another_value",
        },
    )
    workflow_execution_dto = workflow_execution_from_db_to_dto(workflow_execution_db)
    assert isinstance(workflow_execution_dto, WorkflowExecutionDalModel)
    assert workflow_execution_dto.id == workflow_execution_db.id
    assert workflow_execution_dto.workflow_id == workflow_execution_db.workflow_id
    assert (
        workflow_execution_dto.workflow_revision
        == workflow_execution_db.workflow_revision
    )
    assert workflow_execution_dto.tenant_id == workflow_execution_db.tenant_id
    assert workflow_execution_dto.started == workflow_execution_db.started
    assert workflow_execution_dto.triggered_by == workflow_execution_db.triggered_by
    assert workflow_execution_dto.status == workflow_execution_db.status
    assert workflow_execution_dto.is_running == workflow_execution_db.is_running
    assert workflow_execution_dto.timeslot == workflow_execution_db.timeslot
    assert (
        workflow_execution_dto.execution_number
        == workflow_execution_db.execution_number
    )
    assert workflow_execution_dto.error == workflow_execution_db.error
    assert workflow_execution_dto.event_type is None
    assert workflow_execution_dto.event_id is None
    assert workflow_execution_dto.results == workflow_execution_db.results


def test_mapping_workflow_execution_log_db_to_dto():
    workflow_execution_log_db = WorkflowExecutionLog(
        id=1231,
        workflow_execution_id="some workflow_execution_id",
        timestamp=1234567890,
        message="some message",
        context={"key1": "value1", "key2": "value2"},
    )
    workflow_execution_log_dto = workflow_execution_log_from_db_to_dto(
        workflow_execution_log_db
    )
    assert isinstance(workflow_execution_log_dto, WorkflowExecutioLogDalModel)
    assert workflow_execution_log_dto.id == workflow_execution_log_db.id
    assert (
        workflow_execution_log_dto.workflow_execution_id
        == workflow_execution_log_db.workflow_execution_id
    )
    assert workflow_execution_log_dto.timestamp == workflow_execution_log_db.timestamp
    assert workflow_execution_log_dto.message == workflow_execution_log_db.message
    assert workflow_execution_log_dto.context == workflow_execution_log_db.context


def test_mapping_workflow_execution_from_dto_to_db_partial():
    workflow_execution_dto = WorkflowExecutionDalModel(
        id="1",
        workflow_id="workflow_1",
        workflow_revision=1,
        tenant_id="tenant_1",
        started=1234567890,
        triggered_by="user_1",
        status="running",
        is_running=True,
        timeslot=1234567890,
        execution_number=1,
        error=None,
        results={},
        is_test_run=False,
        event_type="alert",
        event_id="some_event_id",
    )
    workflow_execution_partial = workflow_execution_from_dto_to_db_partial(
        workflow_execution_dto
    )
    assert isinstance(workflow_execution_partial, dict)
    assert workflow_execution_partial["id"] == workflow_execution_dto.id
    assert (
        workflow_execution_partial["workflow_id"] == workflow_execution_dto.workflow_id
    )
    assert (
        workflow_execution_partial["workflow_revision"]
        == workflow_execution_dto.workflow_revision
    )
    assert workflow_execution_partial["tenant_id"] == workflow_execution_dto.tenant_id
    assert workflow_execution_partial["started"] == workflow_execution_dto.started
    assert (
        workflow_execution_partial["triggered_by"]
        == workflow_execution_dto.triggered_by
    )
    assert workflow_execution_partial["status"] == workflow_execution_dto.status
    assert workflow_execution_partial["is_running"] == workflow_execution_dto.is_running
    assert workflow_execution_partial["timeslot"] == workflow_execution_dto.timeslot
    assert (
        workflow_execution_partial["execution_number"]
        == workflow_execution_dto.execution_number
    )
    assert workflow_execution_partial["error"] == workflow_execution_dto.error
    assert workflow_execution_partial["results"] == workflow_execution_dto.results
    assert (
        workflow_execution_partial["is_test_run"] == workflow_execution_dto.is_test_run
    )


def test_mapping_workflow_execution_from_dto_to_db_partial_returns_only_explicitly_specified_fields():
    workflow_execution_dto = WorkflowExecutionDalModel(
        id="1",
        workflow_id="workflow_1",
        workflow_revision=1,
        tenant_id="tenant_1",
        started=1234567890,
        triggered_by="user_1",
    )
    workflow_execution_partial = workflow_execution_from_dto_to_db_partial(
        workflow_execution_dto
    )
    assert isinstance(workflow_execution_partial, dict)
    assert len(workflow_execution_partial) == 6
    assert workflow_execution_partial["id"] == workflow_execution_dto.id
    assert (
        workflow_execution_partial["workflow_id"] == workflow_execution_dto.workflow_id
    )
    assert (
        workflow_execution_partial["workflow_revision"]
        == workflow_execution_dto.workflow_revision
    )
    assert workflow_execution_partial["tenant_id"] == workflow_execution_dto.tenant_id
    assert workflow_execution_partial["started"] == workflow_execution_dto.started
    assert (
        workflow_execution_partial["triggered_by"]
        == workflow_execution_dto.triggered_by
    )
