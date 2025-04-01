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
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.facet import FacetType
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto


workflow_field_configurations = [
    FieldMappingConfiguration(map_from_pattern="name", map_to="filter_workflow_name"),
    FieldMappingConfiguration(
        map_from_pattern="description", map_to="filter_workflow_description"
    ),
    FieldMappingConfiguration(map_from_pattern="started", map_to="filter_started"),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_status", map_to="filter_last_execution_status"
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_execution_time", map_to="filter_last_execution_time"
    ),
    FieldMappingConfiguration(
        map_from_pattern="disabled", map_to="filter_workflow_is_disabled"
    ),
    FieldMappingConfiguration(
        map_from_pattern="last_updated", map_to="filter_workflow_last_updated"
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_at", map_to="filter_workflow_creation_time"
    ),
    FieldMappingConfiguration(
        map_from_pattern="created_by", map_to="filter_workflow_created_by"
    ),
    FieldMappingConfiguration(
        map_from_pattern="updated_by", map_to="filter_workflow_updated_by"
    ),
]
alias_column_mapping = {
    "filter_workflow_name": "workflow.name",
    "filter_workflow_description": "workflow.description",
    "filter_workflow_is_disabled": "workflow.is_disabled",
    "filter_workflow_last_updated": "workflow.last_updated",
    "filter_workflow_creation_time": "workflow.creation_time",
    "filter_workflow_updated_by": "workflow.updated_by",
    "filter_started": "started",
    "filter_last_execution_status": "status",
    "filter_last_execution_time": "execution_time",
    "filter_workflow_created_by": "workflow.created_by",
}

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


def __build_base_query(tenant_id: str):
    columns_to_select = []

    for key, value in alias_column_mapping.items():
        if key == "filter_last_execution_status":
            continue
        columns_to_select.append(f"{value} AS {key}")
    latest_executions_subquery_cte = (
        select(
            WorkflowExecution.workflow_id,
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
        .where(
            WorkflowExecution.started
            >= datetime.now(tz=timezone.utc) - timedelta(days=7)
        )
        .cte("latest_executions_subquery")
    )

    workflows_with_last_executions_query = (
        select(
            Workflow,
            Workflow.id.label("entity_id"),
            # here it creates aliases for table columns that will be used in filtering and faceting
            text(",".join(columns_to_select)),
            case(
                (
                    literal_column("status").isnot(None),
                    literal_column("status"),
                ),
                else_="",
            ).label("filter_last_execution_status"),
        )
        .outerjoin(
            latest_executions_subquery_cte,
            and_(
                Workflow.id == latest_executions_subquery_cte.c.workflow_id,
                latest_executions_subquery_cte.c.row_num <= 1,
            ),
        )
        .where(Workflow.tenant_id == tenant_id)
        .where(Workflow.is_deleted == False)
    )

    return {
        "workflows_with_last_executions_query": workflows_with_last_executions_query,
        "latest_executions_subquery_cte": latest_executions_subquery_cte,
    }


def build_workflows_total_count_query(tenant_id: str, cel: str):
    base_query = __build_base_query(tenant_id=tenant_id)[
        "workflows_with_last_executions_query"
    ].cte("base_query")

    query = select(func.count(func.distinct(base_query.c.entity_id))).select_from(
        base_query
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
    fetch_last_executions: int = 15,
):
    limit = limit if limit is not None else 20
    offset = offset if offset is not None else 0
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)
    queries = __build_base_query(tenant_id)
    base_query = select(text("*")).select_from(
        queries["workflows_with_last_executions_query"]
    )

    if not sort_by:
        sort_by = "started"
        sort_dir = "desc"

    order_by_exp = cel_to_sql_instance.get_order_by_expression([(sort_by, sort_dir)])
    base_query = base_query.order_by(text(order_by_exp)).limit(limit).offset(offset)

    if cel:
        sql_filter_str = cel_to_sql_instance.convert_to_sql_str(cel)
        base_query = base_query.filter(text(sql_filter_str))

    base_query = base_query.cte("base_query")

    latest_executions_subquery_cte = queries["latest_executions_subquery_cte"]

    query = (
        select(
            Workflow,
            literal_column("filter_started").label("started"),
            literal_column("filter_last_execution_time").label("execution_time"),
            literal_column("filter_last_execution_status").label("status"),
        )
        .select_from(base_query)
        .join(
            Workflow,
            and_(
                Workflow.id == literal_column("entity_id"),
                Workflow.tenant_id == tenant_id,
            ),
        )
        .outerjoin(
            latest_executions_subquery_cte,
            and_(
                Workflow.id == latest_executions_subquery_cte.c.workflow_id,
                latest_executions_subquery_cte.c.row_num <= fetch_last_executions,
            ),
        )
    )

    return query


def get_workflows_with_last_executions_v2(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    fetch_last_executions: int = 15,
) -> Tuple[list[dict], int]:
    with Session(engine) as session:
        total_count_query = build_workflows_total_count_query(
            tenant_id=tenant_id, cel=cel
        )

        count = session.exec(total_count_query).one()[0]

        if count == 0:
            return [], count

        workflows_query = build_workflows_query(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=fetch_last_executions,
        )

        query_result = session.exec(workflows_query).all()
        result = []
        for workflow, started, execution_time, status in query_result:
            # workaround for filter. In query status is empty string if it is NULL in DB
            status = None if status == "" else status
            result.append(tuple([workflow, started, execution_time, status]))

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

    queries = __build_base_query(tenant_id)

    base_query = select(
        # here it creates aliases for table columns that will be used in filtering and faceting
        text(",".join(["entity_id"] + [key for key in alias_column_mapping.keys()]))
    ).select_from(
        queries["workflows_with_last_executions_query"].cte("workflows_query")
    )

    return get_facet_options(
        base_query=base_query,
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
