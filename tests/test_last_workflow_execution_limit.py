"""
Unit tests for Issue #6905:
Latest workflow execution query lacks LIMIT 1 and materializes large historical results.
"""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine, event
from sqlmodel import Session, SQLModel

from keep.api.core.db import get_last_workflow_execution_by_workflow_id
from keep.api.models.db.workflow import WorkflowExecution
from keep.api.models.db.tenant import Tenant


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        tenant = Tenant(id="tenant-1", name="tenant-1")
        s.add(tenant)
        s.commit()
        yield s


def _create_execution(
    session: Session,
    exec_id: str,
    workflow_id: str,
    tenant_id: str,
    started: datetime,
    status: str = "success",
    execution_number: int = 1,
    results: dict = None,
) -> WorkflowExecution:
    execution = WorkflowExecution(
        id=exec_id,
        workflow_id=workflow_id,
        workflow_revision=1,
        tenant_id=tenant_id,
        started=started,
        triggered_by="scheduler",
        status=status,
        execution_number=execution_number,
        results=results or {"data": "x" * 1024},
    )
    session.add(execution)
    session.commit()
    return execution


def test_get_last_workflow_execution_returns_most_recent(session: Session):
    tenant_id = "tenant-1"
    wf_id = "wf-test-1"
    now = datetime.now()

    _create_execution(
        session, "e1", wf_id, tenant_id, started=now - timedelta(hours=3), execution_number=1
    )
    _create_execution(
        session, "e2", wf_id, tenant_id, started=now - timedelta(hours=1), execution_number=2
    )
    _create_execution(
        session, "e3", wf_id, tenant_id, started=now - timedelta(hours=2), execution_number=3
    )

    last = get_last_workflow_execution_by_workflow_id(
        tenant_id=tenant_id, workflow_id=wf_id, session=session
    )
    assert last is not None
    assert last.id == "e2"


def test_get_last_workflow_execution_filters_by_status(session: Session):
    tenant_id = "tenant-1"
    wf_id = "wf-test-status"
    now = datetime.now()

    _create_execution(
        session, "e1", wf_id, tenant_id, started=now - timedelta(hours=2), status="success", execution_number=1
    )
    _create_execution(
        session, "e2", wf_id, tenant_id, started=now - timedelta(hours=1), status="failed", execution_number=2
    )

    last_success = get_last_workflow_execution_by_workflow_id(
        tenant_id=tenant_id, workflow_id=wf_id, status="success", session=session
    )
    assert last_success is not None
    assert last_success.id == "e1"


def test_get_last_workflow_execution_respects_exclude_ids(session: Session):
    tenant_id = "tenant-1"
    wf_id = "wf-test-exclude"
    now = datetime.now()

    _create_execution(
        session, "e1", wf_id, tenant_id, started=now - timedelta(hours=3), execution_number=1
    )
    _create_execution(
        session, "e2", wf_id, tenant_id, started=now - timedelta(hours=1), execution_number=2
    )

    last = get_last_workflow_execution_by_workflow_id(
        tenant_id=tenant_id, workflow_id=wf_id, exclude_ids=["e2"], session=session
    )
    assert last is not None
    assert last.id == "e1"


def test_get_last_workflow_execution_empty_returns_none(session: Session):
    tenant_id = "tenant-1"
    wf_id = "wf-non-existent"

    last = get_last_workflow_execution_by_workflow_id(
        tenant_id=tenant_id, workflow_id=wf_id, session=session
    )
    assert last is None


def test_get_last_workflow_execution_only_loads_single_entity():
    """Verify that LIMIT 1 prevents ORM entity materialization of historical executions."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    tenant_id = "tenant-1"
    wf_id = "wf-bulk-test"
    now = datetime.now()

    with Session(engine) as s:
        s.add(Tenant(id=tenant_id, name="tenant-1"))
        for i in range(1, 51):
            s.add(
                WorkflowExecution(
                    id=f"bulk-{i}",
                    workflow_id=wf_id,
                    workflow_revision=1,
                    tenant_id=tenant_id,
                    started=now - timedelta(minutes=50 - i),
                    triggered_by="scheduler",
                    status="success",
                    execution_number=i,
                    results={"payload": "x" * 2048},
                )
            )
        s.commit()

    loaded_ids = []

    @event.listens_for(WorkflowExecution, "load")
    def on_load(target, context):
        loaded_ids.append(target.id)

    with Session(engine) as s:
        last = get_last_workflow_execution_by_workflow_id(
            tenant_id=tenant_id, workflow_id=wf_id, session=s
        )
        assert last is not None
        assert last.id == "bulk-50"
        # Crucial check: only exactly 1 entity is materialized into memory by SQL LIMIT 1
        assert len(loaded_ids) == 1
        assert loaded_ids == ["bulk-50"]
