from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict, Tuple, Optional, Any

from sqlalchemy import and_, case, desc, func, select, text
from sqlmodel import Session

from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    PropertiesMetadata,
    PropertyMetadataInfo,
)
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import existed_or_new_session
from keep.api.core.facets import get_facet_options, get_facets
from keep.api.models.db.facet import FacetType
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetDto, FacetOptionDto, FacetOptionsQueryDto
from keep.api.core.cel_to_sql.ast_nodes import DataType


# -----------------------
# Constants / Guardrails
# -----------------------

DEFAULT_LIMIT = 20
MAX_LIMIT = 200

DEFAULT_FETCH_LAST_EXECUTIONS = 15
MAX_FETCH_LAST_EXECUTIONS = 100

DEFAULT_LOOKBACK_DAYS = 30

ALLOWED_SORT_FIELDS = {
    "started",
    "execution_time",
    "status",
    "last_updated",
    "created_at",
    "name",
}
ALLOWED_SORT_DIR = {"asc", "desc"}


def _clamp_int(v: Optional[int], default: int, min_v: int, max_v: int) -> int:
    if v is None:
        return default
    try:
        v = int(v)
    except Exception:
        return default
    if v < min_v:
        return min_v
    if v > max_v:
        return max_v
    return v


# -----------------------
# Metadata
# -----------------------

workflow_field_configurations = [
    FieldMappingConfiguration(map_from_pattern="name", map_to="workflow.name", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="description", map_to="workflow.description", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="started", map_to="started", data_type=DataType.DATETIME),
    FieldMappingConfiguration(map_from_pattern="last_execution_status", map_to="status", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="last_execution_time", map_to="execution_time", data_type=DataType.DATETIME),
    FieldMappingConfiguration(map_from_pattern="disabled", map_to="workflow.is_disabled", data_type=DataType.BOOLEAN),
    FieldMappingConfiguration(map_from_pattern="last_updated", map_to="workflow.last_updated", data_type=DataType.DATETIME),
    FieldMappingConfiguration(map_from_pattern="created_at", map_to="workflow.creation_time", data_type=DataType.DATETIME),
    FieldMappingConfiguration(map_from_pattern="created_by", map_to="workflow.created_by", data_type=DataType.STRING),
    FieldMappingConfiguration(map_from_pattern="updated_by", map_to="workflow.updated_by", data_type=DataType.STRING),
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
        type=FacetType.bool,  # FIX: was str
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


# -----------------------
# Result types
# -----------------------

class ExecutionSummary(TypedDict):
    id: str
    started: datetime
    execution_time: Optional[datetime]
    status: Optional[str]


class WorkflowWithLastExecutions(TypedDict):
    workflow: Workflow
    workflow_last_run_started: Optional[datetime]
    workflow_last_run_time: Optional[datetime]
    workflow_last_run_status: Optional[str]
    workflow_last_executions: list[ExecutionSummary]


# -----------------------
# Query builders
# -----------------------

def _build_workflow_executions_cte(
    tenant_id: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
):
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    return (
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
        .where(WorkflowExecution.is_test_run.is_(False))
        .where(WorkflowExecution.started >= since)
        .cte("workflow_executions")
    )


def build_workflow_executions_query(
    tenant_id: str, workflow_ids: list[str], limit_per_workflow: int
):
    limit_per_workflow = _clamp_int(limit_per_workflow, DEFAULT_FETCH_LAST_EXECUTIONS, 1, MAX_FETCH_LAST_EXECUTIONS)
    executions = _build_workflow_executions_cte(tenant_id)

    return (
        select(
            executions.c.workflow_id,
            executions.c.execution_id,
            executions.c.started,
            executions.c.execution_time,
            executions.c.status,
        )
        .where(executions.c.workflow_id.in_(workflow_ids))
        .where(executions.c.row_num <= limit_per_workflow)
    )


def _build_base_query(
    tenant_id: str,
    executions_cte=None,
    fetch_last_executions: int = 1,
):
    if executions_cte is None:
        executions_cte = _build_workflow_executions_cte(tenant_id)

    fetch_last_executions = _clamp_int(fetch_last_executions, 1, 1, MAX_FETCH_LAST_EXECUTIONS)

    # explicit, non-ambiguous column references
    last_status = case(
        (executions_cte.c.status.isnot(None), executions_cte.c.status),
        else_="",
    ).label("filter_last_execution_status")

    return (
        select(
            Workflow,
            Workflow.id.label("entity_id"),
            executions_cte.c.started.label("started"),
            executions_cte.c.execution_time.label("execution_time"),
            executions_cte.c.status.label("status"),
            executions_cte.c.execution_id.label("execution_id"),
            last_status,
        )
        .select_from(Workflow)
        .outerjoin(
            executions_cte,
            and_(
                Workflow.id == executions_cte.c.workflow_id,
                executions_cte.c.row_num <= fetch_last_executions,
            ),
        )
        .where(Workflow.tenant_id == tenant_id)
        .where(Workflow.is_deleted.is_(False))
        .where(Workflow.is_test.is_(False))
    )


def build_workflows_total_count_query(tenant_id: str, cel: str):
    base = _build_base_query(tenant_id=tenant_id)
    query = select(func.count(func.distinct(Workflow.id))).select_from(base.subquery())

    if cel:
        cel_to_sql = get_cel_to_sql_provider(properties_metadata)
        sql_filter_str = cel_to_sql.convert_to_sql_str(cel)
        # Guardrail: reject obviously unsafe output
        if ";" in sql_filter_str or "--" in sql_filter_str:
            raise ValueError("Unsafe CEL SQL filter output")
        query = query.where(text(sql_filter_str))

    return query


def build_workflows_query(
    tenant_id: str,
    cel: str,
    limit: Optional[int],
    offset: Optional[int],
    sort_by: Optional[str],
    sort_dir: Optional[str],
    fetch_last_executions: int = DEFAULT_FETCH_LAST_EXECUTIONS,
):
    limit = _clamp_int(limit, DEFAULT_LIMIT, 1, MAX_LIMIT)
    offset = _clamp_int(offset, 0, 0, 10_000_000)
    fetch_last_executions = _clamp_int(fetch_last_executions, DEFAULT_FETCH_LAST_EXECUTIONS, 1, MAX_FETCH_LAST_EXECUTIONS)

    executions_cte = _build_workflow_executions_cte(tenant_id)
    query = _build_base_query(
        tenant_id=tenant_id,
        executions_cte=executions_cte,
        fetch_last_executions=1,
    )

    # sort allow-list
    sort_by = (sort_by or "started").strip()
    sort_dir = (sort_dir or "desc").strip().lower()
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "started"
    if sort_dir not in ALLOWED_SORT_DIR:
        sort_dir = "desc"

    cel_to_sql = get_cel_to_sql_provider(properties_metadata)
    order_by_exp = cel_to_sql.get_order_by_expression([(sort_by, sort_dir)])
    if ";" in order_by_exp or "--" in order_by_exp:
        raise ValueError("Unsafe ORDER BY output")

    query = query.order_by(text(order_by_exp)).limit(limit).offset(offset)

    if cel:
        sql_filter_str = cel_to_sql.convert_to_sql_str(cel)
        if ";" in sql_filter_str or "--" in sql_filter_str:
            raise ValueError("Unsafe CEL SQL filter output")
        query = query.where(text(sql_filter_str))

    return query


# -----------------------
# Public API
# -----------------------

def get_workflows_with_last_executions_v2(
    tenant_id: str,
    cel: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_dir: str,
    fetch_last_executions: int = DEFAULT_FETCH_LAST_EXECUTIONS,
    session: Session = None,
) -> Tuple[list[WorkflowWithLastExecutions], int]:
    with existed_or_new_session(session) as session:
        total_count_query = build_workflows_total_count_query(tenant_id=tenant_id, cel=cel)
        count = session.exec(total_count_query).one()[0]

        if count == 0:
            return [], 0

        workflows_query = build_workflows_query(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=1,
        )

        rows = session.exec(workflows_query).all()
        workflow_ids = [workflow.id for workflow, *_ in rows]

        executions_query = build_workflow_executions_query(
            tenant_id=tenant_id,
            workflow_ids=workflow_ids,
            limit_per_workflow=fetch_last_executions,
        )
        exec_rows = session.exec(executions_query).all()

        execution_dict: dict[str, list[ExecutionSummary]] = {}
        for workflow_id, execution_id, started, execution_time, status in exec_rows:
            execution_dict.setdefault(workflow_id, []).append(
                {
                    "id": execution_id,
                    "started": started,
                    "execution_time": execution_time,
                    "status": status,
                }
            )

        result: list[WorkflowWithLastExecutions] = []
        for workflow, started, execution_time, status, execution_id, *_ in rows:
            status = None if status == "" else status
            result.append(
                {
                    "workflow": workflow,
                    "workflow_last_run_started": started,
                    "workflow_last_run_time": execution_time,
                    "workflow_last_run_status": status,
                    "workflow_last_executions": execution_dict.get(workflow.id, []),
                }
            )

        return result, count