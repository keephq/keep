from typing import List, Tuple

from keep.api.core.db import (
    get_previous_execution_id,
    add_or_update_workflow,
    delete_workflow,
    delete_workflow_by_provisioned_file,
    get_all_provisioned_workflows,
    get_all_workflows,
    get_all_workflows_yamls,
    get_timeouted_workflow_exections,
    get_workflow_by_id,
    get_workflow_execution,
    get_workflow_execution_with_logs,
    create_workflow_execution,
    update_workflow_execution,
    get_interval_workflows,
    get_last_completed_execution_without_session,
    get_workflow_execution_by_execution_number,
    get_workflow_version,
    add_workflow_version,
    add_workflow,
)
from keep.workflowmanager.dal.exceptions import ConflictError
from keep.workflowmanager.dal.sql.workflows import (
    get_workflows_with_last_executions_v2,
)

from keep.workflowmanager.dal.sql.mappers import (
    workflow_from_db_to_dto,
    workflow_execution_from_db_to_dto,
    workflow_execution_log_from_db_to_dto,
    workflow_execution_from_dto_to_db_partial,
    workflow_version_from_db_to_dto,
)
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.models.workflowdalmodel import (
    WorkflowDalModel,
    WorkflowVersionDalModel,
    WorkflowWithLastExecutionsDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from sqlalchemy.exc import NoResultFound, IntegrityError

class SqlWorkflowRepository(WorkflowRepository):

    # region Workflow
    def add_workflow(
        self,
        workflow: WorkflowDalModel,
    ) -> WorkflowDalModel:
        db_workflow = add_workflow(
            id=workflow.id,
            name=workflow.name,
            tenant_id=workflow.tenant_id,
            description=workflow.description,
            created_by=workflow.created_by,
            interval=workflow.interval,
            workflow_raw=workflow.workflow_raw,
            is_disabled=workflow.is_disabled,
            updated_by=workflow.updated_by,
            provisioned=workflow.provisioned,
            provisioned_file=workflow.provisioned_file,
            is_test=workflow.is_test,
        )
        return workflow_from_db_to_dto(db_workflow)

    def update_workflow(self, workflow: WorkflowDalModel):
        pass

    def delete_workflow(self, tenant_id, workflow_id):
        delete_workflow(tenant_id=tenant_id, workflow_id=workflow_id)

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        delete_workflow_by_provisioned_file(
            tenant_id=tenant_id, provisioned_file=provisioned_file
        )

    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        return [
            workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_all_provisioned_workflows(tenant_id=tenant_id)
        ]

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
        return [
            workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_all_workflows(
                tenant_id=tenant_id, exclude_disabled=exclude_disabled
            )
        ]

    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        return [
            workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_interval_workflows()
        ]

    def get_all_workflows_yamls(self, tenant_id: str) -> List[str]:
        return get_all_workflows_yamls(tenant_id=tenant_id)

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        db_workflow = get_workflow_by_id(tenant_id=tenant_id, workflow_id=workflow_id)

        if db_workflow is not None:
            return workflow_from_db_to_dto(db_workflow)

        return None

    def get_workflows_with_last_executions_v2(
        self,
        tenant_id: str,
        cel: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_dir: str,
        fetch_last_executions: int = 15,
    ) -> Tuple[list[WorkflowWithLastExecutionsDalModel], int]:
        return get_workflows_with_last_executions_v2(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=fetch_last_executions,
        )

    # endregion

    # region Workflow Version
    def add_workflow_version(self, workflow_version: WorkflowVersionDalModel):
        pass

    def get_workflow_version(
        self, tenant_id: str, workflow_id: str, revision: int
    ) -> WorkflowVersionDalModel | None:
        workflow_version_db = get_workflow_version(
            tenant_id=tenant_id, workflow_id=workflow_id, revision=revision
        )
        if workflow_version_db is None:
            return None

        return workflow_version_from_db_to_dto(workflow_version_db)

    # endregion

    # region Workflow Execution
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
        event_type: str = None,
        test_run: bool = False,
    ) -> str:
        try:
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
        except IntegrityError as e:
            raise ConflictError(
                f"Workflow execution for workflow {workflow_id} with revision {workflow_revision} already exists."
            ) from e

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        if workflow_execution.id is None:
            raise ValueError("Workflow execution ID must not be None")

        update_workflow_execution(
            workflow_execution_patch=workflow_execution_from_dto_to_db_partial(
                workflow_execution_dto=workflow_execution
            )
        )

    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        db_workflow_execution = get_last_completed_execution_without_session(
            workflow_id=workflow_id
        )

        if db_workflow_execution is None:
            return None

        return workflow_execution_from_db_to_dto(db_workflow_execution)

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
            return workflow_execution_from_db_to_dto(db_workflow_execution)
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

        return workflow_execution_log_from_db_to_dto(db_workflow_execution)

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
            workflow_execution_log_from_db_to_dto(item)
            for item in db_workflow_execution_logs
        ]

        return (
            workflow_execution_from_db_to_dto(db_workflow_execution),
            mapped_execution_logs,
        )

    def get_timeouted_workflow_exections(self) -> List[WorkflowExecutionDalModel]:
        db_workflow_executions = get_timeouted_workflow_exections()

        return [
            workflow_execution_from_db_to_dto(db_workflow_execution)
            for db_workflow_execution in db_workflow_executions
        ]

    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        db_workflow_execution = get_workflow_execution_by_execution_number(
            workflow_id=workflow_id, execution_number=execution_number
        )

        if db_workflow_execution is None:
            return None

        return workflow_execution_from_db_to_dto(db_workflow_execution)
    # endregion
