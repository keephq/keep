from datetime import timedelta, datetime, timezone
from typing import List, Tuple

from keep.api.core.cel_to_sql.sql_providers.elastic_search import (
    CelToElasticSearchSqlProvider,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow import WorkflowDoc
from keep.workflowmanager.dal.elasticsearch.models.workflow_execution import (
    WorkflowExecutionDoc,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow_execution_log import (
    WorkflowExecutionLogDoc,
)
from keep.workflowmanager.dal.elasticsearch.models.workflow_version import (
    WorkflowVersionDoc,
)
from keep.workflowmanager.dal.exceptions import ConflictError

from keep.workflowmanager.dal.models.workflowstatsdalmodel import WorkflowStatsDalModel
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
from elasticsearch.helpers import bulk
from keep.workflowmanager.dal.elasticsearch.cel_fields_configuration import (
    properties_metadata,
)
from elasticsearch.dsl import Q, A

class ElasticSearchWorkflowRepository(WorkflowRepository):

    def __init__(self, elastic_search_client: Elasticsearch):
        super().__init__()
        self.elastic_search_client = elastic_search_client
        self.elastic_search_cel_to_sql = CelToElasticSearchSqlProvider(
            properties_metadata
        )

    # region Workflow
    def add_workflow(
        self,
        workflow: WorkflowDalModel,
    ) -> WorkflowDalModel:
        workflow.is_disabled = workflow.is_disabled or False
        doc = WorkflowDoc(**workflow.dict())
        doc.meta.id = workflow.id
        doc.save(
            using=self.elastic_search_client,
            refresh=True,
        )
        return workflow

    def update_workflow(self, workflow: WorkflowDalModel):
        doc = WorkflowDoc(**workflow.dict())
        doc.meta.id = workflow.id
        doc.save(using=self.elastic_search_client, refresh=True)

    def delete_workflow(self, tenant_id, workflow_id):
        self.elastic_search_client.delete(
            index=WorkflowDoc.Index.name,
            id=workflow_id,
            refresh=True,
        )

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        pass

    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        search_result = (
            WorkflowDoc.search(using=self.elastic_search_client)
            .filter("term", is_disabled=False)
            .filter("term", is_deleted=False)
            .filter("range", interval={"gt": 0})
            .execute()
        )

        return [WorkflowDalModel(**item) for item in search_result]

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        result = (
            WorkflowDoc.search(using=self.elastic_search_client)
            .filter("term", tenant_id=tenant_id)
            .filter("term", id=workflow_id)
            .execute()
        )

        doc = result[0] if result else None

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
        query = (
            WorkflowExecutionDoc.search(using=self.elastic_search_client)
            .filter("term", tenant_id=tenant_id)
            .filter("term", workflow_id=workflow_id)
        )

        if triggers:
            for trigger in triggers:
                query = query.filter("match", triggered_by=trigger)

        if statuses:
            query = query.filter("terms", status=statuses)

        if time_delta:
            query = query.filter(
                "range",
                started={
                    "gte": (datetime.now(tz=timezone.utc) - time_delta).isoformat(),
                },
            )

        query.aggs.bucket(
            "success_count", A("filter", term={"status": WorkflowStatus.SUCCESS.value})
        )
        query.aggs.bucket(
            "error_count", A("filter", term={"status": WorkflowStatus.ERROR.value})
        )
        query.aggs.metric("avg_duration", A("avg", field="execution_time"))

        response = query.execute()
        success_count = response.aggregations.success_count.doc_count
        error_count = response.aggregations.error_count.doc_count
        average_duration = response.aggregations.avg_duration.value
        return WorkflowStatsDalModel(
            pass_count=success_count or 0,
            fail_count=error_count or 0,
            avg_duration=average_duration or 0,
        )

    def get_workflows_with_last_executions(
        self,
        tenant_id: str,
        cel: str = "",
        limit: int = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        is_disabled_filter: bool = False,
        is_provisioned_filter: bool = False,
        provisioned_file_filter: str | None = None,
        fetch_last_executions: int = 0,
    ) -> Tuple[list[WorkflowWithLastExecutionsDalModel], int]:
        is_disabled_filter = (
            is_disabled_filter if is_disabled_filter is not None else False
        )
        is_provisioned_filter = (
            is_provisioned_filter if is_provisioned_filter is not None else False
        )
        cel_to_sql_result = self.elastic_search_cel_to_sql.convert_to_sql_str_v2(cel)
        and_exp = f"AND ({cel_to_sql_result.sql})" if cel_to_sql_result.sql else ""

        if is_disabled_filter:
            and_exp += f" AND is_disabled = {'true' if is_disabled_filter else 'false'}"

        if is_provisioned_filter:
            and_exp += (
                f" AND provisioned = {'true' if is_provisioned_filter else 'false'}"
            )

        if provisioned_file_filter:
            and_exp += f" AND provisioned_file = '{provisioned_file_filter}'"

        sort_by_field = None
        if sort_by:
            sort_by_field = (
                properties_metadata.get_property_metadata_for_str(sort_by)
                .field_mappings[0]
                .map_to
                if sort_by
                else "creation_time"
            )
        sort_dir = sort_dir.lower() if sort_dir else "asc"

        limit = limit if limit is not None else 20
        offset = offset if offset is not None else 0

        sql = f"""
                SELECT * FROM "{WorkflowDoc.Index.name}"
                WHERE tenant_id = '{tenant_id}' {and_exp}
                {f'ORDER BY {sort_by_field} {sort_dir}' if sort_by_field else ''}
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
            index=WorkflowDoc.Index.name, body={"query": dsl_query["query"]}
        )

        count = count_response.body.get("count", 0)

        if count == 0:
            return [], 0

        search_result = self.elastic_search_client.search(
            index=WorkflowDoc.Index.name, body=dsl_query
        )

        workflows = []
        for hit in search_result["hits"]["hits"]:
            workflows.append(WorkflowWithLastExecutionsDalModel(**hit["_source"]))

        if fetch_last_executions > 0:
            search_result = (
                WorkflowExecutionDoc.search(using=self.elastic_search_client)
                .filter("term", tenant_id=tenant_id)
                .filter("terms", workflow_id=[workflow.id for workflow in workflows])
                .execute()
            )
            executions = [WorkflowExecutionDalModel(**item) for item in search_result]
            executions_by_workflow = {}
            for execution in executions:
                if execution.workflow_id not in executions_by_workflow:
                    executions_by_workflow[execution.workflow_id] = []
                executions_by_workflow[execution.workflow_id].append(execution)

            for workflow in workflows:
                workflow.workflow_last_executions = executions_by_workflow.get(
                    workflow.id, []
                )[:fetch_last_executions]

        return workflows, count

    # endregion

    # region Workflow Version
    def add_workflow_version(self, workflow_version: WorkflowVersionDalModel):
        try:
            doc = WorkflowVersionDoc(
                **workflow_version.dict(),
            )
            doc.meta.id = f"{workflow_version.workflow_id}-{workflow_version.revision}"
            doc.save(
                using=self.elastic_search_client,
                refresh=True,
            )
        except ElasticsearchConflictError as conflict_error:
            raise ConflictError(
                "Workflow version with the same ID already exists."
            ) from conflict_error

    def get_workflow_version(
        self, tenant_id: str, workflow_id: str, revision: int
    ) -> WorkflowVersionDalModel | None:
        version_id = f"{workflow_id}-{revision}"
        doc = WorkflowVersionDoc.get(id=version_id, using=self.elastic_search_client)
        return WorkflowVersionDalModel(**doc) if doc else None

    def get_workflow_versions(
        self, tenant_id: str, workflow_id: str
    ) -> List[WorkflowVersionDalModel]:
        result = (
            WorkflowVersionDoc.search(using=self.elastic_search_client)
            .filter("term", tenant_id=tenant_id)
            .filter("term", workflow_id=workflow_id)
            .sort("-revision")
            .execute()
        )

        return [WorkflowVersionDalModel(**item) for item in result]

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
        is_test_run = is_test_run if is_test_run is not None else False
        limit = limit if limit is not None else 100
        offset = offset if offset is not None else 0
        query = WorkflowExecutionDoc.search(using=self.elastic_search_client).filter(
            "term", is_test_run=is_test_run
        )

        if tenant_id:
            query = query.filter("term", tenant_id=tenant_id)
        if workflow_id:
            query = query.filter("term", workflow_id=workflow_id)

        if time_delta:
            query = query.filter(
                "range",
                started={
                    "gte": (datetime.now(tz=timezone.utc) - time_delta).isoformat(),
                },
            )

        if triggers:
            query = query.filter("terms", triggered_by=triggers)

        if statuses:
            query = query.filter("terms", status=statuses)
        query = query.sort("-started").extra(size=limit, from_=offset)
        count = query.count()

        if count == 0:
            return [], 0

        search_result = query.execute()
        return [WorkflowExecutionDalModel(**item) for item in search_result], count

    # endregion

    # region Workflow Execution
    def add_workflow_execution(
        self,
        workflow_execution: WorkflowExecutionDalModel,
    ) -> str:
        try:
            workflow_execution.is_test_run = workflow_execution.is_test_run or False
            doc = WorkflowExecutionDoc(**workflow_execution.dict())
            doc.meta.id = workflow_execution.id
            doc.save(
                using=self.elastic_search_client,
                refresh=True,
            )
            return workflow_execution.id
        except ElasticsearchConflictError as conflict_error:
            raise ConflictError(
                "Workflow execution with the same ID already exists."
            ) from conflict_error

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        patch_body = workflow_execution.dict(exclude_unset=True)

        WorkflowExecutionDoc(meta={"id": workflow_execution.id}).update(
            using=self.elastic_search_client, refresh=True, **patch_body
        )

    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        search_result = (
            WorkflowExecutionDoc.search(using=self.elastic_search_client)
            .filter("term", workflow_id=workflow_id)
            .filter("term", is_test_run=False)
            .filter(
                "terms",
                status=[
                    WorkflowStatus.SUCCESS.value,
                    WorkflowStatus.ERROR.value,
                    WorkflowStatus.PROVIDERS_NOT_CONFIGURED.value,
                ],
            )
            .sort("-execution_number")
            .extra(size=1)
        ).execute()

        if not search_result:
            return None

        return WorkflowExecutionDalModel(**search_result[0])

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        search_query = (
            WorkflowExecutionDoc.search(using=self.elastic_search_client)
            .filter("term", id=workflow_execution_id)
            .filter("term", tenant_id=tenant_id)
        )

        if is_test_run is not None:
            search_query = search_query.filter("term", is_test_run=is_test_run)

        search_response = search_query.execute()

        if not search_response:
            return None

        return WorkflowExecutionDalModel(**search_response[0])

    def get_previous_workflow_execution(
        self, tenant_id: str, workflow_id: str, workflow_execution_id: str
    ) -> WorkflowExecutioLogDalModel | None:
        search_result = (
            WorkflowExecutionDoc.search(using=self.elastic_search_client)
            .query(
                "bool",
                must=[
                    Q("term", tenant_id=tenant_id),
                    Q("term", workflow_id=workflow_id),
                    Q("term", is_test_run=False),
                ],
                must_not=[{"term": {"id": workflow_execution_id}}],
            )
            .sort("-started")
            .extra(size=1)
        )
        search_result = search_result.execute()
        if not search_result:
            return None
        return WorkflowExecutioLogDalModel(**search_result[0])

    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        workflow_execution = self.get_workflow_execution(
            tenant_id=tenant_id,
            workflow_execution_id=workflow_execution_id,
            is_test_run=is_test_run,
        )

        if not workflow_execution:
            return None

        logs_search_result = WorkflowExecutionLogDoc.search(
            using=self.elastic_search_client
        ).filter("term", workflow_execution_id=workflow_execution_id)

        logs = []
        index = 0
        for item in logs_search_result:
            log = WorkflowExecutioLogDalModel(**item)
            log.id = index
            logs.append(log)
            index += 1

        return workflow_execution, logs

    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        search_result = (
            WorkflowExecutionDoc.search(using=self.elastic_search_client)
            .filter("term", workflow_id=workflow_id)
            .filter("term", execution_number=execution_number)
            .execute()
        )
        if not search_result:
            return None

        return WorkflowExecutionDalModel(**search_result[0])
    # endregion

    # region Workflow Execution Log
    def add_workflow_execution_logs(
        self, workflow_execution_log: list[WorkflowExecutioLogDalModel]
    ):
        # Convert each to a dict with action metadata
        actions = (
            WorkflowExecutionLogDoc(**log.dict()).to_dict(include_meta=True)
            for log in workflow_execution_log
        )

        # Bulk index
        bulk(self.elastic_search_client, actions)

    # endregion
