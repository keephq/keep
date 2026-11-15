"""Regression coverage for immutable workflow revision timestamps (#5328)."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import update
from sqlalchemy.dialects import mysql, postgresql, sqlite

from keep.api.core.db import (
    add_or_update_workflow,
    get_workflow_versions,
    update_workflow_by_id,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import WorkflowVersion
from keep.api.routes.workflows import list_workflow_versions
from keep.identitymanager.authenticatedentity import AuthenticatedEntity

BASE_TIME = datetime(2020, 1, 1, 12, 0, 0)


def save_workflow(workflow_id, raw, saved_at, **kwargs):
    with patch("keep.api.core.db.datetime") as clock:
        clock.now.return_value = saved_at
        return add_or_update_workflow(
            id=workflow_id,
            name=workflow_id,
            tenant_id=SINGLE_TENANT_UUID,
            description="Revision timestamp regression",
            created_by="creator@example.com",
            updated_by="editor@example.com",
            interval=0,
            workflow_raw=raw,
            is_disabled=False,
            **kwargs,
        )


def test_later_saves_preserve_each_revision_timestamp(db_session):
    """Exercise the bulk is_current update that used to rewrite every old row."""
    times = [BASE_TIME + timedelta(days=day) for day in range(3)]
    for index, saved_at in enumerate(times):
        save_workflow("timestamp-history", f"revision: {index + 1}", saved_at)

    history = get_workflow_versions(SINGLE_TENANT_UUID, "timestamp-history")
    assert [item.revision for item in history] == [3, 2, 1]
    assert [item.updated_at for item in history] == list(reversed(times))
    assert [item.workflow_raw for item in history] == [
        "revision: 3",
        "revision: 2",
        "revision: 1",
    ]
    assert [item.is_current for item in history] == [True, False, False]
    assert all(item.updated_by == "editor@example.com" for item in history)

    # The Versions panel gets these fields from the API, not the ORM identity map.
    response = list_workflow_versions(
        "timestamp-history",
        AuthenticatedEntity(tenant_id=SINGLE_TENANT_UUID, email="viewer@example.com"),
    )
    assert [item.revision for item in response.versions] == [3, 2, 1]
    assert [item.updated_at for item in response.versions] == list(reversed(times))


def test_direct_update_keeps_other_workflow_history_unchanged(db_session):
    save_workflow("first", "revision: 1", BASE_TIME)
    save_workflow("second", "unrelated", BASE_TIME + timedelta(hours=1))
    with patch("keep.api.core.db.datetime") as clock:
        clock.now.return_value = BASE_TIME + timedelta(days=1)
        update_workflow_by_id(
            id="first",
            name="first",
            tenant_id=SINGLE_TENANT_UUID,
            description="Changed description",
            interval=0,
            workflow_raw="revision: 2",
            is_disabled=False,
            updated_by="next-editor@example.com",
        )
    first = get_workflow_versions(SINGLE_TENANT_UUID, "first")
    second = get_workflow_versions(SINGLE_TENANT_UUID, "second")
    assert [item.updated_at for item in first] == [
        BASE_TIME + timedelta(days=1),
        BASE_TIME,
    ]
    assert [item.updated_by for item in first] == [
        "next-editor@example.com",
        "editor@example.com",
    ]
    assert len(second) == 1
    assert second[0].updated_at == BASE_TIME + timedelta(hours=1)
    assert second[0].is_current


def test_identical_save_is_noop_but_force_update_creates_new_timestamp(db_session):
    save_workflow("no-op", "unchanged", BASE_TIME)
    save_workflow("no-op", "unchanged", BASE_TIME + timedelta(days=1))
    history = get_workflow_versions(SINGLE_TENANT_UUID, "no-op")
    assert len(history) == 1
    assert history[0].updated_at == BASE_TIME
    save_workflow(
        "no-op", "unchanged", BASE_TIME + timedelta(days=2), force_update=True
    )
    history = get_workflow_versions(SINGLE_TENANT_UUID, "no-op")
    assert [item.updated_at for item in history] == [
        BASE_TIME + timedelta(days=2),
        BASE_TIME,
    ]
    assert [item.is_current for item in history] == [True, False]


def test_version_metadata_update_preserves_timestamp(db_session):
    save_workflow("metadata", "revision: 1", BASE_TIME)
    version = db_session.get(WorkflowVersion, ("metadata", 1))
    version.is_valid = False
    version.comment = "Validation failed after save"
    db_session.add(version)
    db_session.commit()
    db_session.expire_all()
    reloaded = db_session.get(WorkflowVersion, ("metadata", 1))
    assert reloaded.updated_at == BASE_TIME
    assert reloaded.comment == "Validation failed after save"
    assert not reloaded.is_valid


@pytest.mark.parametrize(
    "dialect", [sqlite.dialect(), postgresql.dialect(), mysql.dialect()]
)
def test_current_flag_update_has_no_implicit_timestamp_assignment(dialect):
    statement = (
        update(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == "workflow-id")
        .values(is_current=False)
    )
    sql = str(statement.compile(dialect=dialect))
    assert "updated_at" not in sql


def test_version_insert_without_explicit_time_uses_database_default(db_session):
    version = WorkflowVersion(
        workflow_id="test-id-1",
        revision=1,
        workflow_raw="default timestamp",
        updated_by="editor@example.com",
        is_valid=True,
        is_current=True,
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    assert isinstance(version.updated_at, datetime)
    saved_at = version.updated_at
    version.is_current = False
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    assert version.updated_at == saved_at
