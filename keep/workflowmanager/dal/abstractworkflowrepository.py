from abc import ABC, abstractmethod
from typing import List, Tuple

from keep.workflowmanager.dal.models.workflowdalmodel import (
    WorkflowDalModel,
    WorkflowWithLastExecutionsDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)


class WorkflowRepository(ABC):
    # region Workflow
    @abstractmethod
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
        pass

    @abstractmethod
    def delete_workflow(self, tenant_id, workflow_id):
        pass

    @abstractmethod
    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    @abstractmethod
    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        pass

    @abstractmethod
    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
        pass

    @abstractmethod
    def get_all_workflows_yamls(self, tenant_id: str):
        pass

    @abstractmethod
    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        pass

    @abstractmethod
    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        """
        Retrieve all workflows that are set to run at regular intervals.

        Returns:
            List[WorkflowDalModel]: A list of workflow data models that are configured for interval execution.
        """

    @abstractmethod
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
        pass

    # endregion

    # region Workflow Execution
    @abstractmethod
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
        pass

    @abstractmethod
    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        pass

    @abstractmethod
    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        pass

    @abstractmethod
    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        pass

    @abstractmethod
    def get_timeouted_workflow_exections(self) -> List[WorkflowExecutionDalModel]:
        pass

    @abstractmethod
    def get_previous_workflow_execution(
        self, tenant_id: str, workflow_id: str, workflow_execution_id: str
    ) -> WorkflowExecutioLogDalModel | None:
        pass

    @abstractmethod
    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        pass

    @abstractmethod
    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        pass

    # endregion
