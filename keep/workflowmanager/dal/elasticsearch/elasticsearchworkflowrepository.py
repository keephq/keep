from datetime import timedelta
from typing import List, Tuple

from keep.api.core.cel_to_sql.sql_providers.elastic_search import (
    CelToElasticSearchSqlProvider,
)
from keep.workflowmanager.dal.exceptions import ConflictError

from keep.workflowmanager.dal.models.workflowstatsdalmodel import WorkflowStatsDalModel
from keep.workflowmanager.dal.sql.mappers import workflow_from_db_to_dto
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.models.workflowdalmodel import (
    WorkflowDalModel,
    WorkflowVersionDalModel,
    WorkflowWithLastExecutionsDalModel,
    WorkflowStatus,
)
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from elasticsearch import (
    # ApiError,
    # BadRequestError,
    Elasticsearch,
    ConflictError as ElasticsearchConflictError,
)
from keep.workflowmanager.dal.elasticsearch.cel_fields_configuration import (
    properties_metadata,
)

class ElasticSearchWorkflowRepository(WorkflowRepository):
    def __init__(self, elastic_search_client: Elasticsearch, index_suffix: str):
        super().__init__()
        self.elastic_search_client = elastic_search_client
        self.workflows_index = f"workflows-{index_suffix}".lower()
        self.workflows_versions_index = f"workflows-versions-{index_suffix}".lower()
        self.workflow_executions_index = f"workflow-executions-{index_suffix}".lower()
        self.workflow_execution_logs_index = (
            f"workflow-execution-logs-{index_suffix}".lower()
        )
        self.elastic_search_cel_to_sql = CelToElasticSearchSqlProvider(
            properties_metadata
        )

    # region Workflow
    def add_workflow(
        self,
        workflow: WorkflowDalModel,
    ) -> WorkflowDalModel:
        self.elastic_search_client.index(
            index=self.workflows_index,
            body=workflow.dict(),
            id=workflow.id,  # we want to update the alert if it already exists so that elastic will have the latest version
            refresh=True,
        )
        return workflow

    def update_workflow(self, workflow: WorkflowDalModel):
        self.elastic_search_client.index(
            index=self.workflows_index,
            body=workflow.dict(),
            id=workflow.id,
            refresh=True,
            op_type="index",
        )

    def delete_workflow(self, tenant_id, workflow_id):
        self.elastic_search_client.delete(
            index=self.workflows_index, id=workflow_id, refresh=True
        )

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    def get_all_provisioned_workflows(self, tenant_id: str) -> List[WorkflowDalModel]:
        return []

    def get_all_workflows(
        self, tenant_id: str, exclude_disabled: bool = False
    ) -> List[WorkflowDalModel]:
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
            workflow_from_db_to_dto(hit["_source"]) for hit in response["hits"]["hits"]
        ]

    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        return []

    def get_all_workflows_yamls(self, tenant_id: str) -> List[str]:
        return []

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        doc = self.__fetch_doc_by_id_from_tenant(
            index_name=self.workflows_index, tenant_id=tenant_id, doc_id=workflow_id
        )
        if not doc:
            return None

        return WorkflowDalModel(**doc)

    def get_workflow_stats(
        self,
        tenant_id: str,
        workflow_id: str,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
    ) -> WorkflowStatsDalModel | None:
        return WorkflowStatsDalModel(
            pass_count=0,
            fail_count=0,
            avg_duration=0,
        )

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
        cel_to_sql_result = self.elastic_search_cel_to_sql.convert_to_sql_str_v2(cel)
        and_exp = f"AND ({cel_to_sql_result.sql})" if cel_to_sql_result.sql else ""

        sort_dir = sort_dir.lower() if sort_dir else "asc"
        sort_by = (
            properties_metadata.get_property_metadata_for_str(sort_by)
            .field_mappings[0]
            .map_to
            if sort_by
            else "creation_time"
        )
        limit = limit if limit is not None else 20
        offset = offset if offset is not None else 0

        sql = f"""
                SELECT * FROM "{self.workflows_index}"
                WHERE tenant_id = '{tenant_id}' {and_exp}
                ORDER BY {sort_by} {sort_dir}
              """
        dsl_query_response = self.elastic_search_client.sql.translate(
            body={"query": sql}
        )
        dsl_query = dict(dsl_query_response)
        dsl_query["_source"] = True
        if offset is not None:
            dsl_query["from"] = offset

        if limit is not None:
            dsl_query["size"] = limit

        count_response = self.elastic_search_client.count(
            index=self.workflows_index, body={"query": dsl_query["query"]}
        )

        count = count_response["count"]

        if count == 0:
            return [], 0

        search_result = self.elastic_search_client.search(
            index=self.workflows_index, body=dsl_query
        )

        workflows = []
        for hit in search_result["hits"]["hits"]:
            workflows.append(WorkflowWithLastExecutionsDalModel(**hit["_source"]))

        return workflows, count

    # endregion

    # region Workflow Version
    def add_workflow_version(self, workflow_version: WorkflowVersionDalModel):
        try:
            version_id = f"{workflow_version.workflow_id}-{workflow_version.revision}"
            self.elastic_search_client.index(
                index=self.workflows_versions_index,
                body=workflow_version.dict(),
                id=version_id,
                refresh=True,
                op_type="create",
            )
        except ElasticsearchConflictError as conflict_error:
            raise ConflictError(
                "Workflow version with the same ID already exists."
            ) from conflict_error

    def get_workflow_version(
        self, tenant_id: str, workflow_id: str, revision: int
    ) -> WorkflowVersionDalModel | None:
        version_id = f"{workflow_id}-{revision}"
        doc = self.__fetch_doc_by_id_from_tenant(
            index_name=self.workflows_versions_index,
            tenant_id=tenant_id,
            doc_id=version_id,
        )
        return WorkflowVersionDalModel(**doc) if doc else None

    def get_workflow_versions(
        self, tenant_id: str, workflow_id: str
    ) -> List[WorkflowVersionDalModel]:
        response = self.elastic_search_client.search(
            index=self.workflows_versions_index,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"tenant_id.keyword": tenant_id}},
                            {"term": {"workflow_id.keyword": workflow_id}},
                        ]
                    }
                },
                "sort": [{"revision": {"order": "desc"}}],
            },
        )
        hits = response["hits"]["hits"]
        return [WorkflowVersionDalModel(**hit["_source"]) for hit in hits]

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
        event_type: str = None,
        test_run: bool = False,
    ) -> str:
        try:
            workflow_execution = WorkflowExecutionDalModel(
                id=execution_id,
                workflow_id=workflow_id,
                workflow_revision=workflow_revision,
                tenant_id=tenant_id,
                triggered_by=triggered_by,
                execution_number=execution_number,
                event_id=event_id,
                fingerprint=fingerprint,
                event_type=event_type,
                test_run=test_run,
            )
            self.elastic_search_client.index(
                index=self.workflow_executions_index,
                body=workflow_execution.dict(),
                id=workflow_execution.id,
                refresh=True,
                op_type="create",
            )
        except ElasticsearchConflictError as conflict_error:
            raise ConflictError(
                "Workflow execution with the same ID already exists."
            ) from conflict_error

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        self.elastic_search_client.index(
            index=self.workflow_executions_index,
            body=workflow_execution.dict(),
            id=workflow_execution.id,
            refresh=True,
            op_type="index",
        )

    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        response = self.elastic_search_client.search(
            index=self.workflow_executions_index,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"workflow_id": workflow_id}},
                            {"term": {"is_test_run": False}},
                            {
                                "terms": {
                                    "status": [
                                        WorkflowStatus.SUCCESS.value,
                                        WorkflowStatus.ERROR.value,
                                        WorkflowStatus.PROVIDERS_NOT_CONFIGURED.value,
                                    ]
                                }
                            },
                        ]
                    }
                },
                "sort": [{"execution_number": {"order": "desc"}}],
                "size": 1,
            },
        )
        hits = response["hits"]["hits"]

        if not hits:
            return None

        return WorkflowExecutionDalModel(**hits[0]["_source"])

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        doc = self.__fetch_doc_by_id_from_tenant(
            index_name=self.workflow_executions_index,
            tenant_id=tenant_id,
            doc_id=workflow_execution_id,
            additional_matches=[{"term": {"is_test_run": is_test_run}}],
        )
        if not doc:
            return None

        return WorkflowExecutionDalModel(**doc)

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

    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        pass

    def __fetch_doc_by_id_from_tenant(
        self,
        index_name: str,
        tenant_id: str,
        doc_id: str,
        additional_matches: dict = None,
    ) -> dict:
        additional_matches = additional_matches if additional_matches else []
        response = self.elastic_search_client.search(
            index=index_name,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"_id": doc_id}},
                            {"term": {"tenant_id": tenant_id}},
                            *additional_matches,
                        ]
                    }
                },
                "size": 1,
            },
        )
        hits = response["hits"]["hits"]

        if not hits:
            return None

        return hits[0]["_source"]

    # endregion
