from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List, Tuple

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


class WorkflowRepository(ABC):
    # region Workflow
    @abstractmethod
    def add_workflow(self, workflow: WorkflowDalModel) -> WorkflowDalModel:
        pass

    @abstractmethod
    def update_workflow(self, workflow: WorkflowDalModel):
        """
        Update an existing workflow.

        Args:
            workflow (WorkflowDalModel): The workflow model to update.
        """

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
    def get_workflows_with_last_executions(
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

    # region Workflow Version
    @abstractmethod
    def add_workflow_version(self, workflow_version: WorkflowVersionDalModel):
        """
        Add a new version of a workflow.

        Args:
            workflow_version (WorkflowVersionDalModel): The workflow version model to add.
        """

    @abstractmethod
    def get_workflow_version(
        self, tenant_id: str, workflow_id: str, revision: int
    ) -> WorkflowVersionDalModel | None:
        """ "
        Retrieve a specific version of a workflow by its ID and revision number.

        Args:
            tenant_id (str): The ID of the tenant.
            workflow_id (str): The ID of the workflow.
            revision (int): The revision number of the workflow.

        Returns:
            WorkflowVersionDalModel | None: The workflow version model if found, otherwise None.
        """

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
    def get_workflow_executions(
        self,
        tenant_id: str,
        workflow_id: str,
        time_delta: timedelta = None,
        statuses: List[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        is_test_run: bool | None = False,
    ) -> list[WorkflowExecutionDalModel] | None:
        """
        Get workflow executions for a specific workflow.
        Args:
            tenant_id (str): The tenant ID.
            workflow_id (str): The workflow ID.
            time_delta (timedelta, optional): Filter executions started within this time delta. Defaults to None, so no time filter is applied.
            statuses (List[str], optional): Filter executions by these statuses. Defaults to None, so all statuses are included.
            limit (int, optional): Limit the number of results. Defaults to 100.
            offset (int, optional): Offset for pagination. Defaults to 0.
            is_test_run (bool, optional): Filter by test runs. Defaults to False, so only non-test runs are included.
        Returns:
            list[WorkflowExecutionDalModel] | None: List of workflow executions or None if not found.
        """

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
