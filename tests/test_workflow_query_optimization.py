"""Query-shape regressions and SQLite results for workflow listing."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlmodel import Session

from keep.api.core import workflows
from keep.api.core.cel_to_sql.sql_providers.base import CelToSqlException
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider_for_dialect,
)
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.facet import FacetOptionsQueryDto


@pytest.mark.parametrize(
    "dialect", [sqlite.dialect(), mysql.dialect(), postgresql.dialect()]
)
@pytest.mark.parametrize(
    "cel,requires_join",
    [
        ("", False),
        ('name == "started last_execution_status"', False),
        ('disabled == false && created_by == "owner"', False),
        ('last_execution_status == "success"', True),
        ('name == "prod" || last_execution_status == "error"', True),
        ("last_execution_time > 2", True),
        ('started > "2026-01-01T00:00:00Z"', True),
    ],
)
def test_count_dependency_query_shape(dialect, cel, requires_join):
    provider = get_cel_to_sql_provider_for_dialect(
        dialect.name, workflows.properties_metadata
    )
    with patch.object(workflows, "get_cel_to_sql_provider", return_value=provider):
        sql = str(
            workflows.build_workflows_total_count_query("tenant", cel).compile(
                dialect=dialect
            )
        )
    assert ("row_number()" in sql) is requires_join
    assert ("JOIN latest_executions_subquery" in sql) is requires_join


def test_invalid_count_filter_raises():
    with pytest.raises(CelToSqlException):
        workflows.build_workflows_total_count_query("tenant", "name ==")


@pytest.mark.parametrize("ids", [["one", "two"], []])
def test_history_ids_restrict_window_input(ids):
    query = workflows.build_workflow_executions_query("tenant", ids, 2)
    inner = query.get_final_froms()[0].element
    sql = str(inner.compile(compile_kwargs={"literal_binds": True}))
    assert "workflowexecution.workflow_id IN" in sql
    assert "workflowexecution.tenant_id = 'tenant'" in sql
    assert "workflowexecution.is_test_run = false" in sql
    assert "workflowexecution.started >=" in sql
    assert all("workflow_id" not in str(clause) for clause in query._where_criteria)


@pytest.mark.parametrize(
    "path,cel,requires_join",
    [
        ("created_by", "", False),
        ("disabled", 'name == "status"', False),
        ("created_by", 'last_execution_status == "success"', True),
        ("last_execution_status", "", True),
        ("started", "", True),
        ("last_execution_time", 'name == "prod"', True),
    ],
)
def test_facet_dependencies(path, cel, requires_join):
    def capture(**kwargs):
        parsed = workflows.get_cel_to_sql_provider(
            workflows.properties_metadata
        ).convert_to_sql_str_v2(cel)
        return kwargs["base_query_factory"](
            path, parsed.involved_fields, [func.count(Workflow.id)]
        )

    with patch.object(workflows, "get_facet_options", side_effect=capture):
        query = workflows.get_workflow_facets_data(
            "tenant", FacetOptionsQueryDto(cel=cel, facet_queries={})
        )
    assert ("row_number()" in str(query)) is requires_join


@pytest.fixture
def query_session():
    engine = create_engine("sqlite://")
    Workflow.__table__.create(engine)
    WorkflowExecution.__table__.create(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for workflow_id, overrides in [
            ("one", {}),
            ("two", {}),
            ("never", {}),
            ("deleted", {"is_deleted": True}),
            ("test", {"is_test": True}),
            ("other", {"tenant_id": "other-tenant"}),
        ]:
            fields = {"tenant_id": "tenant", **overrides}
            session.add(
                Workflow(
                    id=workflow_id,
                    name="prod",
                    created_by="owner",
                    workflow_raw="",
                    **fields
                )
            )
        session.commit()
        for index, (workflow_id, status, days, tenant_id, test_run) in enumerate(
            [
                ("one", "success", 1, "tenant", False),
                ("one", "error", 2, "tenant", False),
                ("one", "error", 0, "tenant", True),
                ("one", "error", 0, "other-tenant", False),
                ("two", "error", 1, "tenant", False),
                ("two", "success", 40, "tenant", False),
            ]
        ):
            session.add(
                WorkflowExecution(
                    id=str(index),
                    workflow_id=workflow_id,
                    tenant_id=tenant_id,
                    status=status,
                    started=now - timedelta(days=days),
                    execution_number=index,
                    is_test_run=test_run,
                    execution_time=10,
                )
            )
        session.commit()
        yield session
    engine.dispose()


@pytest.mark.parametrize(
    "cel,count",
    [
        ("", 3),
        ('name == "prod"', 3),
        ('name == "absent"', 0),
        ('last_execution_status == "success"', 1),
        ('last_execution_status == "error"', 1),
        ('name == "prod" || last_execution_status == "success"', 3),
    ],
)
def test_count_results(query_session, cel, count):
    assert (
        query_session.exec(
            workflows.build_workflows_total_count_query("tenant", cel)
        ).one()[0]
        == count
    )


def test_history_limits_and_exclusions(query_session):
    rows = query_session.exec(
        workflows.build_workflow_executions_query("tenant", ["one", "two"], 1)
    ).all()
    assert {(row.workflow_id, row.execution_id, row.status) for row in rows} == {
        ("one", "0", "success"),
        ("two", "4", "error"),
    }
    rows = query_session.exec(
        workflows.build_workflow_executions_query("tenant", ["one"], 2)
    ).all()
    assert {row.execution_id for row in rows} == {"0", "1"}
    assert (
        query_session.exec(
            workflows.build_workflow_executions_query("tenant", [], 2)
        ).all()
        == []
    )


@pytest.mark.parametrize(
    "cel,count", [("", 3), ('last_execution_status == "success"', 1)]
)
def test_real_facet_builder_results(query_session, cel, count):
    facet = next(f for f in workflows.static_facets if f.property_path == "created_by")
    with patch("keep.api.core.facets.engine", query_session.get_bind()):
        result = workflows.get_workflow_facets_data(
            "tenant", FacetOptionsQueryDto(cel=cel, facet_queries={facet.id: ""})
        )
    assert [(o.value, o.matches_count) for o in result[facet.id]] == [("owner", count)]


def test_workflow_list_retains_execution_columns_and_sort():
    query = workflows.build_workflows_query(
        "tenant", "", limit=20, offset=0, sort_by=None, sort_dir=None
    )
    assert "JOIN latest_executions_subquery" in str(query)
    assert "ORDER BY started DESC" in str(query)
    assert {"started", "execution_time", "status", "execution_id"}.issubset(
        query.selected_columns.keys()
    )
