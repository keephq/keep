"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import and_, case, desc, func, literal_column, select, text
from sqlmodel import Session

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
    PropertyMetadataInfo,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.facet import FacetType
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto
from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.workflowmanager.dal.models.workflowdalmodel import (
    WorkflowWithLastExecutionsDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.sql.mappers import (
    workflow_from_db_to_dto,
)

workflow_field_configurations = [
    FieldMappingConfiguration(
        map_from_pattern="id",
        map_to="workflow.id",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="name",
        map_to="workflow.name",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="description",
        map_to="workflow.description",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="started", map_to="started", data_type=DataType.DATETIME
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_status",
        map_to="status",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_time",
        map_to="execution_time",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="disabled",
        map_to="workflow.is_disabled",
        data_type=DataType.BOOLEAN,
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_updated",
        map_to="workflow.last_updated",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_at",
        map_to="workflow.creation_time",
        data_type=DataType.DATETIME,
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_by",
        map_to="workflow.created_by",
        data_type=DataType.STRING,
    ),
    FieldMappingConfiguration(
        map_from_pattern="updated_by",
        map_to="workflow.updated_by",
        data_type=DataType.STRING,
    ),
]


properties_metadata = PropertiesMetadata(workflow_field_configurations)

static_facets = [
    FacetDto(
        id="558a5844-55a1-45ad-b190-8848a389007d",
        property_path="last_execution_status",
        name="Last execution status",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="6672d434-36d6-4e48-b5ec-3123a7b38cf8",
        property_path="disabled",
        name="Enabling status",
        is_static=True,
        type=FacetType.str,
    ),
    FacetDto(
        id="77325333-7710-4904-bf06-6c3d58aa5787",
        property_path="created_by",
        name="Created by",
        is_static=True,
        type=FacetType.str,
    ),
]
static_facets_dict = {facet.id: facet for facet in static_facets}


def __build_workflow_executions_query(tenant_id: str):
    query = (
        select(
            WorkflowExecution.workflow_id,
            WorkflowExecution.id.label("execution_id"),
            WorkflowExecution.started,
            WorkflowExecution.execution_time,
            WorkflowExecution.status,
            func.row_number()
            .over(
                partition_by=WorkflowExecution.workflow_id,
                order_by=desc(WorkflowExecution.started),
            )
            .label("row_num"),
        )
        .where(WorkflowExecution.tenant_id == tenant_id)
        .where(WorkflowExecution.is_test_run == False)
        .where(
            WorkflowExecution.started
            >= datetime.now(tz=timezone.utc) - timedelta(days=30)
        )
    )

    return query


def build_workflow_executions_query(
    tenant_id: str, workflow_ids: list[str], limit_per_workflow: int
):
    query = __build_workflow_executions_query(tenant_id).cte(
        "workflow_executions_query"
    )

    filtered_query = (
        select(
            query.c.workflow_id,
            query.c.execution_id,
            query.c.started,
            query.c.execution_time,
            query.c.status,
        )
        .select_from(query)
        .where(query.c.workflow_id.in_(workflow_ids))
        .where(query.c.row_num <= limit_per_workflow)
    )

    return filtered_query


def __build_base_query(
    tenant_id: str,
    is_disabled_filter: bool,
    is_provisioned_filter: bool,
    provisioned_file_filter: str,
    select_statements=None,
    latest_executions_subquery_cte=None,
):
    if latest_executions_subquery_cte is None:
        latest_executions_subquery_cte = __build_workflow_executions_query(
            tenant_id
        ).cte("latest_executions_subquery")

    if select_statements is None:
        select_statements = [
            Workflow,
            Workflow.id.label("entity_id"),
            # here it creates aliases for table columns that will be used in filtering and faceting
            case(
                (
                    literal_column("status").isnot(None),
                    literal_column("status"),
                ),
                else_="",
            ).label("filter_last_execution_status"),
        ]

    base_query = (
        select(*select_statements)
        .select_from(Workflow)
        .outerjoin(
            latest_executions_subquery_cte,
            and_(
                Workflow.id == latest_executions_subquery_cte.c.workflow_id,
                latest_executions_subquery_cte.c.row_num <= 1,
            ),
        )
    )

    base_query = (
        base_query.where(Workflow.tenant_id == tenant_id)
        .where(Workflow.is_deleted == False)
        .where(Workflow.is_test == False)
    )

    if is_disabled_filter is not None:
        base_query = base_query.where(Workflow.is_disabled == is_disabled_filter)

    if is_provisioned_filter is not None:
        base_query = base_query.where(Workflow.provisioned == is_provisioned_filter)

    if provisioned_file_filter:
        base_query = base_query.where(
            Workflow.provisioned_file == provisioned_file_filter
        )

    return base_query

    # if latest_executions_subquery_cte is None:
    #     latest_executions_subquery_cte = __build_workflow_executions_query(
    #         tenant_id
    #     ).cte("latest_executions_subquery")

    # if select_statements is None:
    #     select_statements = [
    #         Workflow,
    #         Workflow.id.label("entity_id"),
    #         # here it creates aliases for table columns that will be used in filtering and faceting
    #         case(
    #             (
    #                 literal_column("status").isnot(None),
    #                 literal_column("status"),
    #             ),
    #             else_="",
    #         ).label("filter_last_execution_status"),
    #     ]

    # base_query = (
    #     select(*select_statements)
    #     .select_from(Workflow)
    #     .outerjoin(
    #         latest_executions_subquery_cte,
    #         and_(
    #             Workflow.id == latest_executions_subquery_cte.c.workflow_id,
    #             latest_executions_subquery_cte.c.row_num <= 1,
    #         ),
    #     )
    # )

    # base_query = (
    #     base_query.where(Workflow.tenant_id == tenant_id)
    #     .where(Workflow.is_deleted == False)
    #     .where(Workflow.is_test == False)
    # )

    # if is_disabled_filter is not None:
    #     base_query = base_query.where(Workflow.is_disabled == is_disabled_filter)

    # if is_provisioned_filter is not None:
    #     base_query = base_query.where(Workflow.provisioned == is_provisioned_filter)

    # if provisioned_file_filter:
    #     base_query = base_query.where(
    #         Workflow.provisioned_file == provisioned_file_filter
    #     )

    # return base_query


def build_workflows_total_count_query(
    tenant_id: str,
    cel: str,
    is_disabled_filter: bool,
    is_provisioned_filter: bool,
    provisioned_file_filter: str,
):
    query = __build_base_query(
        tenant_id=tenant_id,
        is_disabled_filter=is_disabled_filter,
        is_provisioned_filter=is_provisioned_filter,
        provisioned_file_filter=provisioned_file_filter,
        select_statements=[func.count(func.distinct(Workflow.id))],
    )

    if cel:
        cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)
        sql_filter_str = cel_to_sql_instance.convert_to_sql_str(cel)
        query = query.filter(text(sql_filter_str))

    query = query.distinct()

    return query


def build_workflows_query(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    is_disabled_filter: bool,
    is_provisioned_filter: bool,
    provisioned_file_filter: str,
):
    limit = limit if limit is not None else 20
    offset = offset if offset is not None else 0
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)
    query = __build_base_query(
        tenant_id=tenant_id,
        is_disabled_filter=is_disabled_filter,
        is_provisioned_filter=is_provisioned_filter,
        provisioned_file_filter=provisioned_file_filter,
        select_statements=[
            Workflow,
            literal_column("started").label("started"),
            literal_column("execution_time").label("execution_time"),
            literal_column("status").label("status"),
            literal_column("execution_id").label("execution_id"),
        ],
    )

    if not sort_by:
        sort_by = "started"
        sort_dir = "desc"

    order_by_exp = cel_to_sql_instance.get_order_by_expression([(sort_by, sort_dir)])
    query = query.order_by(text(order_by_exp)).limit(limit).offset(offset)

    if cel:
        sql_filter_str = cel_to_sql_instance.convert_to_sql_str(cel)
        query = query.filter(text(sql_filter_str))

    return query


def get_workflows_with_last_executions_v2(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    is_disabled_filter: bool,
    is_provisioned_filter: bool,
    provisioned_file_filter: str,
    fetch_last_executions: int,
) -> Tuple[list[WorkflowWithLastExecutionsDalModel], int]:
    with Session(engine) as session:
        total_count_query = build_workflows_total_count_query(
            tenant_id=tenant_id,
            cel=cel,
            is_disabled_filter=is_disabled_filter,
            is_provisioned_filter=is_provisioned_filter,
            provisioned_file_filter=provisioned_file_filter,
        )

        count = session.exec(total_count_query).one()[0]

        if count == 0:
            return [], count

        workflows_query = build_workflows_query(
            tenant_id=tenant_id,
            cel=cel,
            is_disabled_filter=is_disabled_filter,
            is_provisioned_filter=is_provisioned_filter,
            provisioned_file_filter=provisioned_file_filter,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        query_result = session.exec(workflows_query).all()
        workflow_ids = [workflow.id for workflow, *_ in query_result]

        workflow_executions_query_result = []

        if fetch_last_executions is not None and fetch_last_executions > 0:
            workflow_executions_query = build_workflow_executions_query(
                tenant_id=tenant_id,
                workflow_ids=workflow_ids,
                limit_per_workflow=fetch_last_executions,
            )
            workflow_executions_query_result = session.exec(
                workflow_executions_query
            ).all()

        execution_dict = {}
        for (
            workflow_id,
            execution_id,
            started,
            execution_time,
            status,
        ) in workflow_executions_query_result:
            if workflow_id not in execution_dict:
                execution_dict[workflow_id] = []
            execution_dict[workflow_id].append(
                WorkflowExecutionDalModel(
                    id=execution_id,
                    workflow_id=workflow_id,
                    tenant_id=tenant_id,
                    started=started,
                    execution_time=execution_time,
                    status=status,
                )
            )

        result = []
        for workflow, started, execution_time, status, execution_id in query_result:
            # workaround for filter. In query status is empty string if it is NULL in DB
            status = None if status == "" else status
            result.append(
                WorkflowWithLastExecutionsDalModel(
                    workflow_last_run_started=started,
                    workflow_last_run_time=execution_time,
                    workflow_last_run_status=status,
                    workflow_last_executions=execution_dict.get(workflow.id, []),
                    **workflow_from_db_to_dto(workflow).dict()
                )
            )

    return result, count


def get_workflow_facets(
    tenant_id: str, facet_ids_to_load: list[str] = None
) -> list[FacetDto]:
    not_static_facet_ids = []
    facets = []

    if not facet_ids_to_load:
        return static_facets + get_facets(tenant_id, "workflow")

    if facet_ids_to_load:
        for facet_id in facet_ids_to_load:
            if facet_id not in static_facets_dict:
                not_static_facet_ids.append(facet_id)
                continue

            facets.append(static_facets_dict[facet_id])

    if not_static_facet_ids:
        facets += get_facets(tenant_id, "workflow", not_static_facet_ids)

    return facets


def get_workflow_facets_data(
    tenant_id: str,
    facet_options_query: FacetOptionsQueryDto,
) -> dict[str, list[FacetOptionDto]]:
    if facet_options_query and facet_options_query.facet_queries:
        facets = get_workflow_facets(
            tenant_id, facet_options_query.facet_queries.keys()
        )
    else:
        facets = static_facets

    latest_executions_subquery_cte = __build_workflow_executions_query(tenant_id).cte(
        "latest_executions_subquery"
    )

    def base_query_factory(
        facet_property_path: str,
        involved_fields: PropertyMetadataInfo,
        select_statement,
    ):
        return __build_base_query(
            tenant_id=tenant_id,
            select_statements=select_statement,
            latest_executions_subquery_cte=latest_executions_subquery_cte,
            is_disabled_filter=False,
            is_provisioned_filter=False,
            provisioned_file_filter=None,
        )

    return get_facet_options(
        base_query_factory=base_query_factory,
        entity_id_column=Workflow.id,
        facets=facets,
        facet_options_query=facet_options_query,
        properties_metadata=properties_metadata,
    )


def get_workflow_potential_facet_fields(tenant_id: str) -> list[str]:
    return [
        field_configuration.map_from_pattern
        for field_configuration in workflow_field_configurations
        if "*" not in field_configuration.map_from_pattern
    ]
