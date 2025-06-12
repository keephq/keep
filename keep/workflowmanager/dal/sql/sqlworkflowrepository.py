from typing import List, Tuple

from keep.api.core.db import (
    get_previous_execution_id,
    add_or_update_workflow,
    delete_workflow,
    delete_workflow_by_provisioned_file,
    get_all_provisioned_workflows,
    get_all_workflows,
    get_all_workflows_yamls,
    get_workflow_by_id,
    get_workflow_execution,
    get_workflow_execution_with_logs,
    create_workflow_execution,
    update_workflow_execution,
)
from keep.workflowmanager.dal.sql.workflows import (
    WorkflowWithLastExecutions,
    get_workflows_with_last_executions_v2,
)
from keep.api.models.db.workflow import (
    Workflow as WorkflowModel,
    WorkflowExecution,
    WorkflowExecutionLog,
)
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from sqlalchemy.exc import NoResultFound

class SqlWorkflowRepository(WorkflowRepository):

    def add_or_update_workflow(
        self,
        id: str,
        name: str,
        tenant_id: str,
        description: str | None,
        created_by: str,
        interval: int | None,
        workflow_raw: str,
        is_disabled: bool,
        updated_by: str,
        provisioned: bool = False,
        provisioned_file: str | None = None,
        force_update: bool = False,
        is_test: bool = False,
        lookup_by_name: bool = False,
    ) -> WorkflowDalModel:
        db_workflow = add_or_update_workflow(
            id=id,
            name=name,
            tenant_id=tenant_id,
            description=description,
            created_by=created_by,
            interval=interval,
            workflow_raw=workflow_raw,
            is_disabled=is_disabled,
            updated_by=updated_by,
            provisioned=provisioned,
            provisioned_file=provisioned_file,
            force_update=force_update,
            is_test=is_test,
            lookup_by_name=lookup_by_name,
        )
        return self.__workflow_from_db_to_dto(db_workflow)

    def create_workflow_execution(
        self,
        workflow_id: str,
        workflow_revision: int,
        tenant_id: str,
        triggered_by: str,
        execution_number: int = 1,
        event_id: str = None,
        fingerprint: str = None,
        execution_id: str = None,
        event_type: str = "alert",
        test_run: bool = False,
    ) -> str:
        return create_workflow_execution(
            workflow_id=workflow_id,
            workflow_revision=workflow_revision,
            tenant_id=tenant_id,
            triggered_by=triggered_by,
            execution_number=execution_number,
            event_id=event_id,
            fingerprint=fingerprint,
            execution_id=execution_id,
            event_type=event_type,
            test_run=test_run,
        )

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        if workflow_execution.id is None:
            raise ValueError("Workflow execution ID must not be None")

        update_workflow_execution(workflow_execution=workflow_execution)

    def delete_workflow(self, tenant_id, workflow_id):
        delete_workflow(tenant_id=tenant_id, workflow_id=workflow_id)

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        delete_workflow_by_provisioned_file(
            tenant_id=tenant_id, provisioned_file=provisioned_file
        )

    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        return [
            self.__workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_all_provisioned_workflows(tenant_id=tenant_id)
        ]

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
        return [
            self.__workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_all_workflows(
                tenant_id=tenant_id, exclude_disabled=exclude_disabled
            )
        ]

    def get_all_workflows_yamls(self, tenant_id: str) -> List[str]:
        return get_all_workflows_yamls(tenant_id=tenant_id)

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        db_workflow = get_workflow_by_id(tenant_id=tenant_id, workflow_id=workflow_id)

        if db_workflow is not None:
            return self.__workflow_from_db_to_dto(db_workflow)

        return None

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        try:
            db_workflow_execution = get_workflow_execution(
                tenant_id=tenant_id,
                workflow_execution_id=workflow_execution_id,
                is_test_run=is_test_run,
            )
            return self.__workflow_execution_from_db_to_dto(db_workflow_execution)
        except NoResultFound:
            return None

    def get_previous_workflow_execution(
        self, tenant_id: str, workflow_id: str, workflow_execution_id: str
    ) -> WorkflowExecutioLogDalModel | None:
        db_workflow_execution = get_previous_execution_id(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            workflow_execution_id=workflow_execution_id,
        )

        if db_workflow_execution is None:
            return None

        return self.__workflow_execution_log_from_db_to_dto(db_workflow_execution)

    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        try:
            db_workflow_execution, db_workflow_execution_logs = (
                get_workflow_execution_with_logs(
                    tenant_id=tenant_id,
                    workflow_execution_id=workflow_execution_id,
                    is_test_run=is_test_run,
                )
            )
        except NoResultFound:
            return None

        mapped_execution_logs = [
            self.__workflow_execution_log_from_db_to_dto(item)
            for item in db_workflow_execution_logs
        ]

        return (
            self.__workflow_execution_from_db_to_dto(db_workflow_execution),
            mapped_execution_logs,
        )

    def get_workflows_with_last_executions_v2(
        self,
        tenant_id: str,
        cel: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_dir: str,
        fetch_last_executions: int = 15,
    ) -> Tuple[list[WorkflowWithLastExecutions], int]:
        return get_workflows_with_last_executions_v2(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=fetch_last_executions,
        )

    def __workflow_from_db_to_dto(self, db_workflow: WorkflowModel) -> WorkflowDalModel:
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

    def __workflow_execution_from_db_to_dto(
        self, db_workflow_execution: WorkflowExecution
    ) -> WorkflowExecutionDalModel:
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
        )

    def __workflow_execution_log_from_db_to_dto(
        self, db_workflow_execution_log: WorkflowExecutionLog
    ) -> WorkflowExecutionDalModel:
        return WorkflowExecutioLogDalModel(
            id=db_workflow_execution_log.id,
            workflow_execution_id=db_workflow_execution_log.workflow_execution_id,
            timestamp=db_workflow_execution_log.timestamp,
            message=db_workflow_execution_log.message,
            context=db_workflow_execution_log.context,
        )
