"""Retention correctness against real PostgreSQL constraints and transactions."""

import importlib.util
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import event, func, select, text

from keep.api.core.workflow_retention import RetentionPolicy, run_retention
from keep.api.models.db.workflow import (
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowToAlertExecution,
    WorkflowToIncidentExecution,
)

NOW = datetime(2026, 11, 12, 12)

EXECUTIONS = WorkflowExecution.__table__
LOGS = WorkflowExecutionLog.__table__
ALERT_LINKS = WorkflowToAlertExecution.__table__
INCIDENT_LINKS = WorkflowToIncidentExecution.__table__
INDEX = "idx_workflowexecutionlog_workflow_execution_id"


def ids(engine):
    with engine.connect() as connection:
        return set(connection.execute(select(EXECUTIONS.c.id)).scalars())


def count(engine, table):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(table))


@pytest.mark.parametrize(
    "field,value",
    [
        ("success_days", -1),
        ("success_days", 0),
        ("failure_days", 0),
        ("batch_size", 0),
        ("batch_size", 1001),
        ("log_batch_size", 0),
        ("log_batch_size", 10001),
        ("keep_successes", 0),
        ("batch_pause_ms", -1),
        ("max_runtime_seconds", 0),
        ("statement_timeout_ms", 0),
        ("success_log_days", 31),
    ],
)
def test_reject_invalid_policy(field, value):
    with pytest.raises(ValueError):
        RetentionPolicy(**{field: value})


def test_scope_is_required(pg_engine):
    with pytest.raises(ValueError):
        run_retention(pg_engine, RetentionPolicy(), now=NOW)
    with pytest.raises(ValueError):
        run_retention(
            pg_engine, RetentionPolicy(), tenant_id="a", all_tenants=True, now=NOW
        )


def test_dry_run_counts_all_batches_without_mutations(pg_engine, seed):
    for number in range(5):
        seed(f"old-{number}", logs=2, associations=True)
    seed("recent", days=1)
    statements = []

    def record(_, __, statement, *args):
        statements.append(statement)

    event.listen(pg_engine, "before_cursor_execute", record)
    report = run_retention(
        pg_engine,
        RetentionPolicy(batch_size=2, keep_successes=1),
        tenant_id="tenant-a",
        now=NOW,
    )
    assert report["completed"]
    assert report["eligible_executions"] == 5
    assert report["eligible_logs"] == 10
    assert report["eligible_alert_associations"] == 5
    assert report["eligible_incident_associations"] == 5
    assert count(pg_engine, EXECUTIONS) == 6
    assert count(pg_engine, LOGS) == 10
    assert not any(
        s.lstrip().upper().startswith(("DELETE", "UPDATE", "INSERT"))
        for s in statements
    )


def test_apply_removes_children_preserves_recent_active_and_other_tenant(
    pg_engine, seed
):
    seed("old", logs=7, associations=True)
    seed("failed", days=45, status="error", logs=1, associations=True)
    seed("recent", days=1)
    seed("active", days=60, status="in_progress", execution_time=None, logs=1)
    seed("timeout", days=60, status="timeout", execution_time=None)
    seed("ambiguous", days=60, execution_time=None)
    seed("other", tenant="tenant-b", workflow="wf-b", logs=1)
    report = run_retention(
        pg_engine,
        RetentionPolicy(batch_size=1, log_batch_size=2, keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert report["completed"]
    assert report["deleted_executions"] == 2
    assert report["deleted_logs"] == 8
    assert report["deleted_alert_associations"] == 2
    assert report["deleted_incident_associations"] == 2
    assert ids(pg_engine) == {"recent", "active", "timeout", "ambiguous", "other"}
    assert count(pg_engine, LOGS) == 2
    again = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert again["deleted_executions"] == 0


def test_protect_latest_successes_and_scheduler_record_even_when_old(pg_engine, seed):
    seed("old-success-1", days=100)
    seed("old-success-2", days=90)
    seed("test-success", days=80, is_test=True)
    seed("last-completed", days=70, status="error")
    report = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=2),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert report["deleted_executions"] == 1
    assert ids(pg_engine) == {"old-success-1", "old-success-2", "last-completed"}


def test_failure_retention_and_real_completion_time(pg_engine, seed):
    seed("old", days=20)
    seed("recent-failure", days=20, status="error")
    seed("old-failure", days=40, status="error")
    seed("long-running", days=40, execution_time=39 * 86400)
    seed("recent", days=1)
    run_retention(
        pg_engine,
        RetentionPolicy(success_days=14, failure_days=30, keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert ids(pg_engine) == {"recent-failure", "long-running", "recent"}


def test_success_log_retention_keeps_parent_and_failure_logs(pg_engine, seed):
    seed("success", days=10, logs=7)
    seed("error", days=10, status="error", logs=3)
    seed("recent", days=1)
    report = run_retention(
        pg_engine,
        RetentionPolicy(
            success_days=14, success_log_days=7, log_batch_size=2, keep_successes=1
        ),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert report["deleted_executions"] == 0
    assert report["deleted_logs"] == 7
    assert count(pg_engine, EXECUTIONS) == 3
    assert count(pg_engine, LOGS) == 3


def test_missing_log_index_refuses_apply(pg_engine, seed):
    seed("old", logs=1)
    seed("recent", days=1)
    with pg_engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{INDEX}"'))
    with pytest.raises(ValueError, match="index"):
        run_retention(
            pg_engine, RetentionPolicy(), tenant_id="tenant-a", apply=True, now=NOW
        )
    assert count(pg_engine, EXECUTIONS) == 2
    assert count(pg_engine, LOGS) == 1


def test_unknown_inbound_dependency_refuses_cleanup(pg_engine, seed):
    seed("old")
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE future_dependency (id integer PRIMARY KEY, execution_id varchar REFERENCES workflowexecution(id))"
            )
        )
    with pytest.raises(ValueError, match="depend"):
        run_retention(
            pg_engine, RetentionPolicy(), tenant_id="tenant-a", apply=True, now=NOW
        )


def test_rollback_does_not_delete_parent_or_associations(pg_engine, seed):
    seed("old", associations=True)
    seed("recent", days=1)

    def fail(_, __, statement, *args):
        if statement.startswith("DELETE FROM workflowexecution "):
            raise RuntimeError("injected failure before parent deletion")

    event.listen(pg_engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        run_retention(
            pg_engine,
            RetentionPolicy(keep_successes=1),
            tenant_id="tenant-a",
            apply=True,
            now=NOW,
        )
    event.remove(pg_engine, "before_cursor_execute", fail)
    assert count(pg_engine, EXECUTIONS) == 2
    assert count(pg_engine, ALERT_LINKS) == 1
    assert count(pg_engine, INCIDENT_LINKS) == 1


def test_all_tenants_are_processed_with_separate_protection(pg_engine, seed):
    for tenant, workflow in [("tenant-a", "wf-a"), ("tenant-b", "wf-b")]:
        seed(tenant + "-old", tenant=tenant, workflow=workflow)
        seed(tenant + "-recent", tenant=tenant, workflow=workflow, days=1)
    report = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        all_tenants=True,
        apply=True,
        now=NOW,
    )
    assert report["deleted_executions"] == 2
    assert ids(pg_engine) == {"tenant-a-recent", "tenant-b-recent"}


def test_cli_invalid_arguments_and_help_do_not_load_application_db(monkeypatch):
    path = (
        Path(__file__).resolve().parents[2] / "keep" / "cli" / "workflow_retention.py"
    )
    spec = importlib.util.spec_from_file_location("retention_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for arguments, code in [
        (["--help"], 0),
        ([], 2),
        (["--tenant-id", "tenant-a", "--retention-days", "-1"], 2),
    ]:
        with pytest.raises(SystemExit) as error:
            module.main(arguments)
        assert error.value.code == code


def test_association_fanout_is_bounded(pg_engine, seed):
    seed("old")
    seed("recent", days=1)
    with pg_engine.begin() as connection:
        connection.execute(
            ALERT_LINKS.insert(),
            [
                dict(workflow_execution_id="old", alert_fingerprint=f"a-{n}")
                for n in range(9)
            ],
        )
    report = run_retention(
        pg_engine,
        RetentionPolicy(log_batch_size=2, keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert report["deleted_alert_associations"] == 9
    assert report["deleted_executions"] == 1
    assert report["committed_batches"] == 5


def test_runtime_limit_reports_committed_progress_and_can_resume(
    pg_engine, seed, monkeypatch
):
    from keep.api.core import workflow_retention

    for number in range(3):
        seed(f"old-{number}")
    seed("recent", days=1)
    clock = [0.0]
    monkeypatch.setattr(workflow_retention.time, "monotonic", lambda: clock[0])

    def advance(_, __, statement, *args):
        if statement.startswith("DELETE FROM workflowexecution "):
            clock[0] += 2

    event.listen(pg_engine, "after_cursor_execute", advance)
    report = run_retention(
        pg_engine,
        RetentionPolicy(batch_size=1, keep_successes=1, max_runtime_seconds=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    event.remove(pg_engine, "after_cursor_execute", advance)
    assert not report["completed"]
    assert report["stop_reason"] == "runtime_limit"
    assert report["deleted_executions"] == 1
    assert count(pg_engine, EXECUTIONS) == 3
    resumed = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert resumed["deleted_executions"] == 2


def test_query_timeout_marks_preview_incomplete(pg_engine, seed):
    seed("old")
    seed("recent", days=1)

    def slow_count(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT count("):
            return "SELECT pg_sleep(0.1)", ()
        return statement, parameters

    event.listen(pg_engine, "before_cursor_execute", slow_count, retval=True)
    report = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1, statement_timeout_ms=10),
        tenant_id="tenant-a",
        now=NOW,
    )
    event.remove(pg_engine, "before_cursor_execute", slow_count)
    assert not report["completed"]
    assert report["stop_reason"] == "query_timeout"
    assert report["deleted_executions"] == 0
    assert count(pg_engine, EXECUTIONS) == 2


def test_apply_never_selects_result_payload(pg_engine, seed):
    seed("old", result={"large": "x" * 100000})
    seed("recent", days=1)
    statements = []

    def record(_, __, statement, *args):
        statements.append(statement)

    event.listen(pg_engine, "before_cursor_execute", record)
    run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert not any("workflowexecution.results" in s for s in statements)


def test_terminal_provider_configuration_error_is_eligible(pg_engine, seed):
    seed("old", status="providers_not_configured")
    seed("recent", days=1)
    report = run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert report["deleted_executions"] == 1


def test_cli_success_uses_synchronous_engine(pg_engine, seed, monkeypatch, capsys):
    import json

    path = (
        Path(__file__).resolve().parents[2] / "keep" / "cli" / "workflow_retention.py"
    )
    spec = importlib.util.spec_from_file_location("retention_cli_success", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed("old", days=365)
    seed("recent", days=0)
    monkeypatch.setattr(module, "_get_engine", lambda: pg_engine)
    assert module.main(["--tenant-id", "tenant-a", "--keep-successes", "1"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry-run"
    assert report["eligible_executions"] == 1
    assert count(pg_engine, EXECUTIONS) == 2


@pytest.mark.parametrize(
    "entrypoint",
    [
        ["-m", "keep.cli.workflow_retention"],
        ["scripts/cleanup_workflow_executions.py"],
    ],
)
def test_packaged_and_source_cli_help(entrypoint):
    result = subprocess.run(
        [sys.executable, *entrypoint, "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--apply" in result.stdout


def test_zero_candidates_preview_is_complete(pg_engine):
    report = run_retention(pg_engine, RetentionPolicy(), all_tenants=True, now=NOW)
    assert report["completed"]
    assert report["eligible_executions"] == 0
    assert report["eligible_logs"] == 0


def test_keep_failed_preserves_old_errors(pg_engine, seed):
    seed("error", status="error", logs=2)
    seed("recent", days=1)
    run_retention(
        pg_engine,
        RetentionPolicy(failure_days=None, keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    assert ids(pg_engine) == {"error", "recent"}
    assert count(pg_engine, LOGS) == 2


def test_protected_checkpoint_is_not_rewritten(pg_engine, seed):
    payload = {
        "sync-slow-query-patterns": [{"checkpoint_base64": "b3BhcXVl", "delivered": 0}],
        "extra": [1, 2, 3],
    }
    seed("protected", days=100, logs=2, result=payload)
    seed("old-test", days=90, is_test=True)
    run_retention(
        pg_engine,
        RetentionPolicy(keep_successes=1),
        tenant_id="tenant-a",
        apply=True,
        now=NOW,
    )
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                select(EXECUTIONS.c.results).where(EXECUTIONS.c.id == "protected")
            )
            == payload
        )
    assert count(pg_engine, LOGS) == 2


def test_missing_fk_refuses_apply(pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE workflowexecutionlog DROP CONSTRAINT workflowexecutionlog_workflow_execution_id_fkey"
            )
        )
    with pytest.raises(ValueError, match="depend"):
        run_retention(
            pg_engine, RetentionPolicy(), tenant_id="tenant-a", apply=True, now=NOW
        )


def test_partial_log_index_is_not_accepted(pg_engine, seed):
    seed("old")
    with pg_engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{INDEX}"'))
        connection.execute(
            text(
                f'CREATE INDEX "{INDEX}" ON workflowexecutionlog(workflow_execution_id) WHERE workflow_execution_id IS NOT NULL'
            )
        )
    with pytest.raises(ValueError, match="index"):
        run_retention(
            pg_engine, RetentionPolicy(), tenant_id="tenant-a", apply=True, now=NOW
        )


@pytest.mark.parametrize(
    "parent",
    ["workflowexecutionlog", "workflowtoalertexecution", "workflowtoincidentexecution"],
)
def test_unknown_history_child_dependency_refuses_cascading_delete(
    pg_engine, seed, parent
):
    seed("old", logs=1, associations=True)
    seed("recent", days=1)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE TABLE future_child_dependency (id integer PRIMARY KEY, history_id integer REFERENCES {parent}(id) ON DELETE CASCADE)"
            )
        )
    with pytest.raises(ValueError, match="depend"):
        run_retention(
            pg_engine,
            RetentionPolicy(keep_successes=1),
            tenant_id="tenant-a",
            apply=True,
            now=NOW,
        )
    assert count(pg_engine, LOGS) == 1
    assert count(pg_engine, ALERT_LINKS) == 1
    assert count(pg_engine, INCIDENT_LINKS) == 1
