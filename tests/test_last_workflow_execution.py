from datetime import datetime, timedelta

from sqlalchemy import event

from keep.api.core import db as db_module
from keep.api.core.db import get_last_workflow_execution_by_workflow_id
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import WorkflowExecution


def _workflow_execution(
    execution_id: str,
    *,
    started: datetime,
    status: str = "success",
    workflow_id: str = "test-id-2",
    tenant_id: str = SINGLE_TENANT_UUID,
    execution_number: int = 1,
) -> WorkflowExecution:
    return WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        started=started,
        triggered_by="test",
        status=status,
        execution_number=execution_number,
        error=None,
        execution_time=1,
        results={"payload": "x" * 1024},
    )


def test_get_last_workflow_execution_limits_loaded_rows(db_session):
    now = datetime.utcnow()
    db_session.add_all(
        [
            _workflow_execution(
                "oldest", started=now - timedelta(minutes=30), execution_number=1
            ),
            _workflow_execution(
                "middle", started=now - timedelta(minutes=20), execution_number=2
            ),
            _workflow_execution(
                "newest", started=now - timedelta(minutes=10), execution_number=3
            ),
        ]
    )
    db_session.commit()

    loaded_ids = []
    statements = []

    @event.listens_for(WorkflowExecution, "load")
    def on_load(target, _context):
        loaded_ids.append(target.id)

    @event.listens_for(db_module.engine, "before_cursor_execute")
    def before_cursor_execute(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        if "FROM workflowexecution" in statement:
            statements.append(statement)

    try:
        result = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "test-id-2"
        )
    finally:
        event.remove(WorkflowExecution, "load", on_load)
        event.remove(db_module.engine, "before_cursor_execute", before_cursor_execute)

    assert result is not None
    assert result.id == "newest"
    assert loaded_ids == ["newest"]
    assert any("LIMIT" in statement.upper() for statement in statements)


def test_get_last_workflow_execution_preserves_filters(db_session):
    now = datetime.utcnow()
    db_session.add_all(
        [
            _workflow_execution(
                "latest-error",
                started=now - timedelta(minutes=1),
                status="error",
                execution_number=10,
            ),
            _workflow_execution(
                "latest-success",
                started=now - timedelta(minutes=2),
                execution_number=9,
            ),
            _workflow_execution(
                "previous-success",
                started=now - timedelta(minutes=3),
                execution_number=8,
            ),
            _workflow_execution(
                "too-old",
                started=now - timedelta(days=2),
                execution_number=7,
            ),
            _workflow_execution(
                "other-workflow",
                started=now,
                workflow_id="test-id-1",
                execution_number=6,
            ),
            _workflow_execution(
                "other-tenant",
                started=now,
                tenant_id="other-tenant",
                execution_number=5,
            ),
        ]
    )
    db_session.commit()

    assert (
        get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "test-id-2", status="success"
        ).id
        == "latest-success"
    )
    assert (
        get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID,
            "test-id-2",
            status="success",
            exclude_ids=["latest-success"],
        ).id
        == "previous-success"
    )
    assert (
        get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "test-id-2", status="missing"
        )
        is None
    )
