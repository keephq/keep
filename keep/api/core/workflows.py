"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, func, literal_column, select, text
from sqlmodel import Session

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine
from keep.api.models.db.facet import FacetType
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetDto


workflow_field_configurations = [
    FieldMappingConfiguration("name", "workflow.name"),
    FieldMappingConfiguration("description", "workflow.description"),
]
alias_column_mapping = {
    "filter_last_received": "alert.timestamp",
}

properties_metadata = PropertiesMetadata(workflow_field_configurations)

static_facets = [
    FacetDto(
        id="f8a91ac7-4916-4ad0-9b46-a5ddb85bfbb8",
        property_path="severity",
        name="Severity",
        is_static=True,
        type=FacetType.str,
    ),
]
static_facets_dict = {facet.id: facet for facet in static_facets}


def __build_base_query(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    fetch_last_executions: int = 15,
):
    latest_executions_subquery = (
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
            latest_executions_subquery.c.started,
            latest_executions_subquery.c.execution_time,
            latest_executions_subquery.c.status,
        )
        .outerjoin(
            latest_executions_subquery,
            and_(
                Workflow.id == latest_executions_subquery.c.workflow_id,
                latest_executions_subquery.c.row_num <= fetch_last_executions,
            ),
        )
        .where(Workflow.tenant_id == tenant_id)
        .where(Workflow.is_deleted == False)
    )

    return workflows_with_last_executions_query


def get_workflows_with_last_executions_v2(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    fetch_last_executions: int = 15,
) -> list[dict]:
    cel_to_sql_instance = get_cel_to_sql_provider(properties_metadata)

    # List first 1000 worflows and thier last executions in the last 7 days which are active)
    with Session(engine) as session:
        base_query = (
            __build_base_query(
                tenant_id, cel, limit, offset, sort_by, sort_dir, fetch_last_executions
            )
            .order_by(Workflow.id, desc(literal_column("started")))
            .distinct()
            .limit(15000)
        )

        if cel:
            sql_filter_str = cel_to_sql_instance.convert_to_sql_str(cel)
            base_query = base_query.filter(text(sql_filter_str))

        result = session.execute(base_query).all()

    return result
