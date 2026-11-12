"""Exercise the actual Alembic index revision outside application startup."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

PATH = (
    Path(__file__).resolve().parents[2]
    / "keep/api/models/db/migrations/versions/2026-11-12-13-30_6942a1b2c3d4.py"
)
INDEX = "idx_workflowexecutionlog_workflow_execution_id"


def revision():
    spec = importlib.util.spec_from_file_location("workflow_retention_index", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(engine, direction):
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with context.begin_transaction():
            with Operations.context(context):
                getattr(revision(), direction)()


def test_concurrent_index_upgrade_is_idempotent_and_downgrade_works(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{INDEX}"'))
    migrate(pg_engine, "upgrade")
    migrate(pg_engine, "upgrade")
    assert INDEX in {
        i["name"] for i in inspect(pg_engine).get_indexes("workflowexecutionlog")
    }
    migrate(pg_engine, "downgrade")
    assert INDEX not in {
        i["name"] for i in inspect(pg_engine).get_indexes("workflowexecutionlog")
    }


def test_invalid_index_requires_explicit_repair(pg_engine, seed):
    seed("old", logs=2)
    with pg_engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{INDEX}"'))
    with pg_engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    f'CREATE UNIQUE INDEX CONCURRENTLY "{INDEX}" ON workflowexecutionlog(workflow_execution_id)'
                )
            )
    with pytest.raises(RuntimeError, match="Inspect/repair"):
        migrate(pg_engine, "upgrade")


def test_accepts_prebuilt_equivalent_index(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{INDEX}"'))
        connection.execute(
            text(
                "CREATE INDEX prebuilt_execution_lookup ON workflowexecutionlog(workflow_execution_id)"
            )
        )
    migrate(pg_engine, "upgrade")
    names = {i["name"] for i in inspect(pg_engine).get_indexes("workflowexecutionlog")}
    assert "prebuilt_execution_lookup" in names
    assert INDEX not in names


def test_revision_has_one_head():
    # Validate the revision graph without importing unrelated historical migration
    # modules (which require the entire application's optional provider stack).
    import ast

    root = Path(__file__).resolve().parents[2]
    revisions, parents = set(), set()
    for path in (root / "keep/api/models/db/migrations/versions").glob("*.py"):
        metadata = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in (
                        "revision",
                        "down_revision",
                    ):
                        metadata[target.id] = ast.literal_eval(node.value)
        if "revision" in metadata:
            revisions.add(metadata["revision"])
            parent = metadata.get("down_revision")
            parents.update(
                parent if isinstance(parent, tuple) else [parent] if parent else []
            )
    assert parents <= revisions
    assert revisions - parents == {"6942a1b2c3d4"}


def test_sqlite_migration_upgrade_and_downgrade_remain_compatible(tmp_path):
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE workflowexecutionlog (id integer PRIMARY KEY, workflow_execution_id varchar NOT NULL)"
                )
            )
        migrate(engine, "upgrade")
        migrate(engine, "upgrade")
        assert INDEX in {
            i["name"] for i in inspect(engine).get_indexes("workflowexecutionlog")
        }
        migrate(engine, "downgrade")
        assert INDEX not in {
            i["name"] for i in inspect(engine).get_indexes("workflowexecutionlog")
        }
    finally:
        engine.dispose()
