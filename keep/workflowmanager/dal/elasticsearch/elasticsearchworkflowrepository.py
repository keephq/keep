from typing import List, Tuple

from keep.workflowmanager.dal.exceptions import ConflictError
from keep.workflowmanager.dal.sql.workflows import (
    WorkflowWithLastExecutions,
)

from keep.workflowmanager.dal.sql.mappers import workflow_from_db_to_dto
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.models.workflowdalmodel import WorkflowDalModel
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from elasticsearch import ApiError, BadRequestError, Elasticsearch


class ElasticSearchWorkflowRepository(WorkflowRepository):
    def __init__(self, elastic_search_client: Elasticsearch, index_suffix: str):
        super().__init__()
        self.elastic_search_client = elastic_search_client
        self.workflows_index = f"workflows-{index_suffix}"
        self.workflow_executions_index = f"workflow-executions-{index_suffix}"
        self.workflow_execution_logs_index = f"workflow-execution-logs-{index_suffix}"

    # region Workflow
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
        self.elastic_search_client.index(
            index=self.workflows_index,
            body=WorkflowDalModel(
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
            ),
            id=id,  # we want to update the alert if it already exists so that elastic will have the latest version
            refresh=True,
        )

    def delete_workflow(self, tenant_id, workflow_id):
        self.elastic_search_client.delete(
            self.workflows_index, id=workflow_id, refresh=True
        )

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        return []

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
        try:
            response = self.elastic_search_client.search(
                index=self.workflows_index,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"tenant_id": tenant_id}},
                                {"term": {"is_disabled": exclude_disabled}},
                            ]
                        }
                    }
                },
            )
            return [
                workflow_from_db_to_dto(hit["_source"])
                for hit in response["hits"]["hits"]
            ]
        except (ApiError, BadRequestError) as e:
            raise ConflictError(f"Error retrieving workflows: {str(e)}")

    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        return []

    def get_all_workflows_yamls(self, tenant_id: str) -> List[str]:
        return []

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
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
    ) -> Tuple[list[WorkflowWithLastExecutions], int]:
        return [], 0

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
        event_type: str = "alert",
        test_run: bool = False,
    ) -> str:
        self.elastic_search_client.index(
            index=self.workflow_executions_index,
            body=WorkflowExecutionDalModel(
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
            ),
            id=execution_id or f"{workflow_id}-{execution_number}",
            refresh=True,
        )

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        pass

    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        pass

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        pass

    def get_previous_workflow_execution(
        self, tenant_id: str, workflow_id: str, workflow_execution_id: str
    ) -> WorkflowExecutioLogDalModel | None:
        pass

    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        pass

    def get_timeouted_workflow_exections(self) -> List[WorkflowExecutionDalModel]:
        pass

    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        pass

    # endregion
