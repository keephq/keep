from keep.api.models.db.workflow import WorkflowExecution, WorkflowExecutionLog
from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)


def workflow_from_db_to_dto(db_workflow: WorkflowDalModel) -> WorkflowDalModel:
    return WorkflowDalModel(
        id=db_workflow.id,
        tenant_id=db_workflow.tenant_id,
        name=db_workflow.name,
        description=db_workflow.description,
        created_by=db_workflow.created_by,
        creation_time=db_workflow.creation_time,
        interval=db_workflow.interval,
        workflow_raw=db_workflow.workflow_raw,
        is_deleted=db_workflow.is_deleted,
        is_disabled=db_workflow.is_disabled,
        revision=db_workflow.revision,
        last_updated=db_workflow.last_updated,
        provisioned=db_workflow.provisioned,
        provisioned_file=db_workflow.provisioned_file,
        is_test=db_workflow.is_test,
    )


def workflow_execution_from_db_to_dto(
    db_workflow_execution: WorkflowExecution,
) -> WorkflowExecutionDalModel:
    event_type = None
    event_id = None

    if db_workflow_execution.workflow_to_alert_execution:
        event_type = "alert"
        event_id = db_workflow_execution.workflow_to_alert_execution.event_id

    if db_workflow_execution.workflow_to_incident_execution:
        event_type = "incident"
        event_id = db_workflow_execution.workflow_to_incident_execution.incident_id

    return WorkflowExecutionDalModel(
        id=db_workflow_execution.id,
        workflow_id=db_workflow_execution.workflow_id,
        workflow_revision=db_workflow_execution.workflow_revision,
        tenant_id=db_workflow_execution.tenant_id,
        started=db_workflow_execution.started,
        triggered_by=db_workflow_execution.triggered_by,
        status=db_workflow_execution.status,
        is_running=db_workflow_execution.is_running,
        timeslot=db_workflow_execution.timeslot,
        execution_number=db_workflow_execution.execution_number,
        error=db_workflow_execution.error,
        execution_time=db_workflow_execution.execution_time,
        results=db_workflow_execution.results,
        is_test_run=db_workflow_execution.is_test_run,
        event_type=event_type,
        event_id=event_id,
    )


def workflow_execution_from_dto_to_db_partial(
    workflow_execution_dto: WorkflowExecutionDalModel,
) -> dict:
    result = {}

    for key, value in workflow_execution_dto.dict(exclude_unset=True).items():
        if hasattr(WorkflowExecution, key):
            result[key] = value

    return result


def workflow_execution_log_from_db_to_dto(
    db_workflow_execution_log: WorkflowExecutionLog,
) -> WorkflowExecutionDalModel:
    return WorkflowExecutioLogDalModel(
        id=db_workflow_execution_log.id,
        workflow_execution_id=db_workflow_execution_log.workflow_execution_id,
        timestamp=db_workflow_execution_log.timestamp,
        message=db_workflow_execution_log.message,
        context=db_workflow_execution_log.context,
    )
