from abc import ABC, abstractmethod
from typing import List, Tuple

from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from keep.workflowmanager.dal.sql.workflows import WorkflowWithLastExecutions


class WorkflowRepository(ABC):
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
    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        """
        Retrieve a workflow execution record based on the provided identifiers.

        Args:
            tenant_id (str): The unique identifier for the tenant.
            workflow_execution_id (str): The unique identifier for the workflow execution.
            is_test_run (bool | None, optional): Indicates whether the workflow execution
                is a test run. Defaults to None.

        Returns:
            WorkflowExecutionDalModel | None: The workflow execution data model if found,
                otherwise None.
        """

    @abstractmethod
    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        """
        Retrieve a workflow execution along with its associated logs.

        Args:
            tenant_id (str): The ID of the tenant to which the workflow execution belongs.
            workflow_execution_id (str): The unique identifier of the workflow execution.
            is_test_run (bool | None, optional): Indicates whether the workflow execution is a test run.
                Defaults to None.

        Returns:
            tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
                A tuple containing the workflow execution data model and a list of associated log data models,
                or None if no matching workflow execution is found.
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
    ) -> Tuple[list[WorkflowWithLastExecutions], int]:
        pass
