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
from keep.workflowmanager.dal.models.workflowstatsdalmodel import WorkflowStatsDalModel


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
        """
        Delete a workflow by its ID.

        Args:
            tenant_id (str): The ID of the tenant.
            workflow_id (str): The ID of the workflow to delete.
        """

    @abstractmethod
    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    @abstractmethod
    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        pass

    @abstractmethod
    def get_workflow_stats(
        self,
        tenant_id: str,
        workflow_id: str,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
    ) -> WorkflowStatsDalModel | None:
        """
        Retrieve statistics for a specific workflow.
        Args:
            tenant_id (str): The ID of the tenant.
            workflow_id (str): The ID of the workflow.
            time_delta (timedelta, optional): Filter statistics for executions started within this time delta. Defaults to None, so no time filter is applied.
            triggers (List[str], optional): Filter statistics by these triggers. Defaults to None, so all triggers are included.
            statuses (List[str], optional): Filter statistics by these statuses. Defaults to None, so all statuses are included.
        Returns:
            WorkflowStatsDalModel | None: The statistics model for the workflow, or None if not found.
        """

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
        cel: str = "",
        limit: int = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        is_disabled_filter: bool = None,
        is_provisioned_filter: bool = None,
        provisioned_file_filter: str | None = None,
        fetch_last_executions: int = None,
    ) -> Tuple[list[WorkflowWithLastExecutionsDalModel], int]:
        """
        Retrieve workflows with their last executions.

        Args:
            tenant_id (str): The ID of the tenant.
            cel (str, optional): CEL filter string. Defaults to "".
            limit (int, optional): Maximum number of workflows to return. Defaults to None, which means no limit.
            offset (int, optional): Offset for pagination. Defaults to 0.
            sort_by (str, optional): Field to sort by. Defaults to "created_at".
            sort_dir (str, optional): Sort direction ("asc" or "desc"). Defaults to "desc".
            is_disabled_filter (bool, optional): Filter for disabled workflows. Defaults to None, which means no filter.
            is_provisioned_filter (bool, optional): Filter for provisioned workflows. Defaults to None, which means no filter.
            provisioned_file_filter (str | None, optional): Filter by provisioned file name. Defaults to None.
            fetch_last_executions (int, optional): Number of last executions to fetch for each workflow. Defaults to None, which means no last executions are fetched.

        Returns:
            Tuple[list[WorkflowWithLastExecutionsDalModel], int]: A tuple containing a list of workflows with their last executions and the total count of workflows.
        """

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

    @abstractmethod
    def get_workflow_versions(
        self, tenant_id: str, workflow_id: str
    ) -> List[WorkflowVersionDalModel]:
        """
        Retrieve all versions of active workflow.
        Args:
            tenant_id (str): The ID of the tenant.
            workflow_id (str): The ID of the workflow.
        Returns:
            List[WorkflowVersionDalModel]: A list of workflow version models.
        """

    # endregion

    # region Workflow Execution
    @abstractmethod
    def add_workflow_execution(
        self,
        workflow_execution: WorkflowExecutionDalModel,
    ) -> str:
        """
        Add a new workflow execution.

        Args:
            workflow_execution (WorkflowExecutionDalModel): The workflow execution model to add.

        Returns:
            str: The ID of the added workflow execution.
        """

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
        tenant_id: str | None,
        workflow_id: str | None,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
        is_test_run: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[list[WorkflowExecutioLogDalModel], int]:
        """
        Get workflow executions for a specific workflow.
        Args:
            tenant_id (str): The tenant ID. If not specified, workflow executions for all tenants will be returned.
            workflow_id (str): The workflow ID. If not specified, workflow executions for all workflows will be returned.
            time_delta (timedelta, optional): Filter executions started within this time delta. Defaults to None, so no time filter is applied.
            triggers (List[str], optional): Filter executions by these triggers. Defaults to None, so all triggers are included.
            statuses (List[str], optional): Filter executions by these statuses. Defaults to None, so all statuses are included.
            limit (int, optional): Limit the number of results. Defaults to 100.
            offset (int, optional): Offset for pagination. Defaults to 0.
            is_test_run (bool, optional): Filter by test runs. Defaults to False, so only non-test runs are included.
        Returns:
            Tuple[list[WorkflowExecutioLogDalModel], int]: A tuple containing a list of workflow execution logs and the total count of executions.
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

    # region Workflow Execution Log
    @abstractmethod
    def add_workflow_execution_logs(
        self, workflow_execution_log: list[WorkflowExecutioLogDalModel]
    ):
        """
        Add logs for a workflow execution.

        Args:
            workflow_execution_log (list[WorkflowExecutioLogDalModel]): A list of workflow execution log models to add.
        """

    # endregion
