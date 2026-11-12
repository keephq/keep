"""Isolated PostgreSQL tests; never use Keep's application connection string."""

import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel

from keep.api.models.db.tenant import Tenant
from keep.api.models.db.workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowToAlertExecution,
    WorkflowToIncidentExecution,
    WorkflowVersion,
)

NOW = datetime(2026, 11, 12, 12)


@pytest.fixture
def pg_engine():
    url = os.getenv("KEEP_RETENTION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set KEEP_RETENTION_TEST_DATABASE_URL to an isolated PostgreSQL DB")
    admin = create_engine(url)
    schema = "keep_retention_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, connect_args={"options": f"-c search_path={schema},public"}
    )
    tables = [
        Tenant.__table__,
        Workflow.__table__,
        WorkflowVersion.__table__,
        WorkflowExecution.__table__,
        WorkflowExecutionLog.__table__,
        WorkflowToAlertExecution.__table__,
        WorkflowToIncidentExecution.__table__,
    ]
    SQLModel.metadata.create_all(engine, tables=tables)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def seed(pg_engine):
    tenants, workflows = set(), set()
    sequence = 0

    def add(
        identifier,
        *,
        days=45,
        status="success",
        tenant="tenant-a",
        workflow="wf-a",
        is_test=False,
        execution_time=1,
        logs=0,
        associations=False,
        result=None,
    ):
        nonlocal sequence
        sequence += 1
        with pg_engine.begin() as connection:
            if tenant not in tenants:
                connection.execute(
                    Tenant.__table__.insert().values(id=tenant, name=tenant)
                )
                tenants.add(tenant)
            if workflow not in workflows:
                connection.execute(
                    Workflow.__table__.insert().values(
                        id=workflow,
                        tenant_id=tenant,
                        name=workflow,
                        created_by="retention-test",
                        workflow_raw="{}",
                        interval=60,
                    )
                )
                workflows.add(workflow)
            connection.execute(
                WorkflowExecution.__table__.insert().values(
                    id=identifier,
                    tenant_id=tenant,
                    workflow_id=workflow,
                    status=status,
                    started=NOW - timedelta(days=days),
                    triggered_by="scheduler",
                    execution_number=sequence,
                    execution_time=execution_time,
                    is_test_run=is_test,
                    is_running=12345 if status != "in_progress" else 1,
                    results=result or {"checkpoint": identifier},
                )
            )
            for number in range(logs):
                connection.execute(
                    WorkflowExecutionLog.__table__.insert().values(
                        workflow_execution_id=identifier,
                        timestamp=NOW - timedelta(days=days),
                        message=f"test log {number}",
                        context={},
                    )
                )
            if associations:
                connection.execute(
                    WorkflowToAlertExecution.__table__.insert().values(
                        workflow_execution_id=identifier,
                        alert_fingerprint="alert-1",
                    )
                )
                connection.execute(
                    WorkflowToIncidentExecution.__table__.insert().values(
                        workflow_execution_id=identifier,
                        incident_id="incident-1",
                    )
                )
        return identifier

    return add
