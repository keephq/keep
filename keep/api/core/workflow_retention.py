"""Opt-in PostgreSQL workflow-history maintenance, independent of the scheduler."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, exists, func, or_, select, text
from sqlalchemy.exc import DBAPIError

from keep.api.models.db.workflow import (
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowToAlertExecution,
    WorkflowToIncidentExecution,
)

logger = logging.getLogger(__name__)
EXECUTIONS = WorkflowExecution.__table__
LOGS = WorkflowExecutionLog.__table__
ALERT_LINKS = WorkflowToAlertExecution.__table__
INCIDENT_LINKS = WorkflowToIncidentExecution.__table__
COMPLETED_STATUSES = ("success", "error", "providers_not_configured")


@dataclass(frozen=True)
class RetentionPolicy:
    success_days: int = 30
    failure_days: int | None = 30
    success_log_days: int | None = None
    keep_successes: int = 5
    batch_size: int = 100
    log_batch_size: int = 5000
    batch_pause_ms: int = 200
    max_runtime_seconds: int = 600
    statement_timeout_ms: int = 15000
    lock_timeout_ms: int = 1000

    def __post_init__(self):
        limits = {
            "success_days": 36500,
            "keep_successes": 100,
            "batch_size": 1000,
            "log_batch_size": 10000,
            "max_runtime_seconds": 3600,
            "statement_timeout_ms": 600000,
            "lock_timeout_ms": 60000,
        }
        for name, maximum in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be between 1 and {maximum}")
        if (
            type(self.batch_pause_ms) is not int
            or not 0 <= self.batch_pause_ms <= 10000
        ):
            raise ValueError("batch_pause_ms must be between 0 and 10000")
        for name in ("failure_days", "success_log_days"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not int or not 1 <= value <= 36500
            ):
                raise ValueError(f"{name} must be a positive number of days")
        if (
            self.success_log_days is not None
            and self.success_log_days > self.success_days
        ):
            raise ValueError("success_log_days cannot exceed success_days")


class _BudgetExpired(Exception):
    pass


def _timeouts(connection, policy, deadline):
    remaining = int((deadline - time.monotonic()) * 1000)
    if remaining <= 0:
        raise _BudgetExpired
    connection.execute(
        select(
            func.set_config(
                "statement_timeout",
                str(min(policy.statement_timeout_ms, remaining)),
                True,
            )
        )
    )
    connection.execute(
        select(
            func.set_config(
                "lock_timeout",
                str(min(policy.lock_timeout_ms, remaining)),
                True,
            )
        )
    )


def _preflight(connection):
    """Refuse unadapted dependencies or an unindexed foreign-key lookup."""
    dependencies = connection.execute(
        text(
            """
        SELECT child.relname, attribute.attname, constraint_info.convalidated,
                   constraint_info.conrelid IN (
                       to_regclass('workflowexecutionlog'),
                       to_regclass('workflowtoalertexecution'),
                       to_regclass('workflowtoincidentexecution')
                   ) AS known_table
        FROM pg_constraint constraint_info
        JOIN pg_class child ON child.oid = constraint_info.conrelid
        JOIN pg_attribute attribute ON attribute.attrelid = child.oid
            AND attribute.attnum = ANY(constraint_info.conkey)
        WHERE constraint_info.contype = 'f'
          AND constraint_info.confrelid = to_regclass('workflowexecution')
    """
        )
    ).all()
    if any(
        not row.known_table
        or not row.convalidated
        or row.attname != "workflow_execution_id"
        for row in dependencies
    ):
        raise ValueError(
            "Unadapted inbound workflowexecution dependency; inspect the schema"
        )
    if {row.relname for row in dependencies} != {
        LOGS.name,
        ALERT_LINKS.name,
        INCIDENT_LINKS.name,
    }:
        raise ValueError(
            "Missing workflowexecution dependency constraints; inspect the schema"
        )
    child_dependencies = connection.scalar(
        text(
            """
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE contype = 'f' AND confrelid IN (
                to_regclass('workflowexecutionlog'),
                to_regclass('workflowtoalertexecution'),
                to_regclass('workflowtoincidentexecution')
            )
        )
    """
        )
    )
    if child_dependencies:
        raise ValueError(
            "Unadapted inbound history-child dependency; inspect the schema"
        )
    for table in (LOGS, ALERT_LINKS, INCIDENT_LINKS):
        indexed = connection.scalar(
            text(
                """
            SELECT EXISTS (
                SELECT 1 FROM pg_index index_info
                JOIN pg_attribute attribute
                    ON attribute.attrelid = index_info.indrelid
                    AND attribute.attnum = index_info.indkey[0]
                WHERE index_info.indrelid = to_regclass(:table_name)
                  AND index_info.indisvalid AND index_info.indisready
                  AND index_info.indpred IS NULL
                  AND attribute.attname = 'workflow_execution_id'
            )
        """
            ),
            {"table_name": table.name},
        )
        if not indexed:
            raise ValueError(
                f"A valid non-partial index beginning with workflow_execution_id "
                f"is required on {table.name}; prepare the index separately"
            )


def _protected_ids(connection, tenant_id, keep_successes):
    success = (
        select(
            EXECUTIONS.c.id,
            func.row_number()
            .over(
                partition_by=EXECUTIONS.c.workflow_id,
                order_by=(EXECUTIONS.c.started.desc(), EXECUTIONS.c.id.desc()),
            )
            .label("position"),
        )
        .where(
            EXECUTIONS.c.tenant_id == tenant_id,
            EXECUTIONS.c.status == "success",
            EXECUTIONS.c.is_test_run.is_(False),
        )
        .subquery()
    )
    completed = (
        select(
            EXECUTIONS.c.id,
            func.row_number()
            .over(
                partition_by=EXECUTIONS.c.workflow_id,
                order_by=(
                    EXECUTIONS.c.execution_number.desc(),
                    EXECUTIONS.c.started.desc(),
                    EXECUTIONS.c.id.desc(),
                ),
            )
            .label("position"),
        )
        .where(
            EXECUTIONS.c.tenant_id == tenant_id,
            EXECUTIONS.c.status.in_(COMPLETED_STATUSES),
            EXECUTIONS.c.is_test_run.is_(False),
        )
        .subquery()
    )
    protected = set(
        connection.execute(
            select(success.c.id).where(success.c.position <= keep_successes)
        ).scalars()
    )
    protected.update(
        connection.execute(
            select(completed.c.id).where(completed.c.position == 1)
        ).scalars()
    )
    return protected


def _old_completed(statuses, cutoff):
    # The indexed started predicate is retained as a cheap preliminary filter.
    # is_running is a scheduler sentinel/random integer, not a completion boolean.
    return and_(
        EXECUTIONS.c.status.in_(statuses),
        EXECUTIONS.c.started < cutoff,
        EXECUTIONS.c.execution_time >= 0,
        EXECUTIONS.c.started + EXECUTIONS.c.execution_time * text("INTERVAL '1 second'")
        < cutoff,
    )


def _predicates(policy, tenant_id, protected, now):
    scope = and_(EXECUTIONS.c.tenant_id == tenant_id, EXECUTIONS.c.id.not_in(protected))
    success = _old_completed(("success",), now - timedelta(days=policy.success_days))
    terminal = [success]
    if policy.failure_days is not None:
        terminal.append(
            _old_completed(
                ("error", "providers_not_configured"),
                now - timedelta(days=policy.failure_days),
            )
        )
    parents = and_(scope, or_(*terminal))
    log_parents = parents
    logs = parents
    if policy.success_log_days is not None:
        cutoff = now - timedelta(days=policy.success_log_days)
        early_success = and_(scope, _old_completed(("success",), cutoff))
        log_parents = or_(parents, early_success)
        logs = or_(parents, and_(early_success, LOGS.c.timestamp < cutoff))
    return parents, log_parents, logs


def _preview(connection, report, parents, logs, policy, deadline):
    operations = [
        (
            "eligible_executions",
            select(func.count()).select_from(EXECUTIONS).where(parents),
        ),
        (
            "stored_results_bytes",
            select(
                func.coalesce(func.sum(func.pg_column_size(EXECUTIONS.c.results)), 0)
            ).where(parents),
        ),
        (
            "eligible_logs",
            select(func.count())
            .select_from(
                LOGS.join(EXECUTIONS, LOGS.c.workflow_execution_id == EXECUTIONS.c.id)
            )
            .where(logs),
        ),
        (
            "eligible_alert_associations",
            select(func.count())
            .select_from(
                ALERT_LINKS.join(
                    EXECUTIONS, ALERT_LINKS.c.workflow_execution_id == EXECUTIONS.c.id
                )
            )
            .where(parents),
        ),
        (
            "eligible_incident_associations",
            select(func.count())
            .select_from(
                INCIDENT_LINKS.join(
                    EXECUTIONS,
                    INCIDENT_LINKS.c.workflow_execution_id == EXECUTIONS.c.id,
                )
            )
            .where(parents),
        ),
    ]
    for key, statement in operations:
        _timeouts(connection, policy, deadline)
        value = connection.scalar(statement)
        report[key] = (report[key] or 0) + value


def _delete_batch(connection, policy, parents, log_parents, logs):
    """Never materialize results/log bodies; limit children separately."""
    has_logs = exists(
        select(LOGS.c.id)
        .where(
            LOGS.c.workflow_execution_id == EXECUTIONS.c.id,
            logs,
        )
        .correlate(EXECUTIONS)
    )
    log_parent_ids = list(
        connection.execute(
            select(EXECUTIONS.c.id)
            .where(log_parents, has_logs)
            .order_by(EXECUTIONS.c.started, EXECUTIONS.c.id)
            .limit(policy.batch_size)
        ).scalars()
    )
    deleted = {
        "deleted_logs": 0,
        "deleted_executions": 0,
        "deleted_alert_associations": 0,
        "deleted_incident_associations": 0,
    }
    if log_parent_ids:
        log_ids = (
            select(LOGS.c.id)
            .select_from(
                LOGS.join(EXECUTIONS, LOGS.c.workflow_execution_id == EXECUTIONS.c.id)
            )
            .where(
                EXECUTIONS.c.id.in_(log_parent_ids),
                logs,
            )
            .limit(policy.log_batch_size)
        )
        deleted["deleted_logs"] = connection.execute(
            delete(LOGS).where(LOGS.c.id.in_(log_ids))
        ).rowcount
    no_logs = ~exists(
        select(LOGS.c.id).where(LOGS.c.workflow_execution_id == EXECUTIONS.c.id)
    )
    parent_ids = list(
        connection.execute(
            select(EXECUTIONS.c.id)
            .where(parents, no_logs)
            .order_by(EXECUTIONS.c.started, EXECUTIONS.c.id)
            .limit(policy.batch_size)
        ).scalars()
    )
    if parent_ids:
        for table, key in (
            (ALERT_LINKS, "deleted_alert_associations"),
            (INCIDENT_LINKS, "deleted_incident_associations"),
        ):
            association_ids = (
                select(table.c.id)
                .where(table.c.workflow_execution_id.in_(parent_ids))
                .limit(policy.log_batch_size)
            )
            deleted[key] = connection.execute(
                delete(table).where(table.c.id.in_(association_ids))
            ).rowcount
        no_alert_links = ~exists(
            select(ALERT_LINKS.c.id).where(
                ALERT_LINKS.c.workflow_execution_id == EXECUTIONS.c.id
            )
        )
        no_incident_links = ~exists(
            select(INCIDENT_LINKS.c.id).where(
                INCIDENT_LINKS.c.workflow_execution_id == EXECUTIONS.c.id
            )
        )
        deleted["deleted_executions"] = connection.execute(
            delete(EXECUTIONS).where(
                EXECUTIONS.c.id.in_(parent_ids),
                parents,
                no_logs,
                no_alert_links,
                no_incident_links,
            )
        ).rowcount
    return deleted


def run_retention(
    engine, policy, *, tenant_id=None, all_tenants=False, apply=False, now=None
):
    """Run against PostgreSQL; dry-run is read-only and incomplete reports are explicit.

    No schema modification, checkpoint rewriting, alert deletion, or VACUUM is done.
    Counts from apply mode describe committed work, not an estimate of total scope.
    """
    if bool(tenant_id) == bool(all_tenants) or (
        tenant_id is not None and not tenant_id.strip()
    ):
        raise ValueError("Choose exactly one nonempty tenant_id or all_tenants")
    if engine.dialect.name != "postgresql":
        raise ValueError("Workflow retention currently requires PostgreSQL")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    deadline = time.monotonic() + policy.max_runtime_seconds
    report = {
        "mode": "apply" if apply else "dry-run",
        "checked_at_utc": now.isoformat() + "Z",
        "completed": False,
        "stop_reason": None,
        "tenants": 0,
        "protected_executions": 0,
        "eligible_executions": None,
        "eligible_logs": None,
        "stored_results_bytes": None,
        "eligible_alert_associations": None,
        "eligible_incident_associations": None,
        "deleted_executions": 0,
        "deleted_logs": 0,
        "deleted_alert_associations": 0,
        "deleted_incident_associations": 0,
        "committed_batches": 0,
    }
    try:
        with engine.connect() as connection:
            # A preview uses one bounded, consistent read-only snapshot.
            with connection.begin():
                connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                _timeouts(connection, policy, deadline)
                _preflight(connection)
                tenants = (
                    [tenant_id]
                    if tenant_id
                    else list(
                        connection.execute(
                            select(EXECUTIONS.c.tenant_id)
                            .distinct()
                            .order_by(EXECUTIONS.c.tenant_id)
                        ).scalars()
                    )
                )
                protections = {}
                for tenant in tenants:
                    _timeouts(connection, policy, deadline)
                    protections[tenant] = _protected_ids(
                        connection, tenant, policy.keep_successes
                    )
                    report["protected_executions"] += len(protections[tenant])
                    if not apply:
                        parents, _, logs = _predicates(
                            policy, tenant, protections[tenant], now
                        )
                        _preview(connection, report, parents, logs, policy, deadline)
                    report["tenants"] += 1
            if apply:
                for tenant in tenants:
                    parents, log_parents, logs = _predicates(
                        policy, tenant, protections[tenant], now
                    )
                    while True:
                        with connection.begin():
                            _timeouts(connection, policy, deadline)
                            deleted = _delete_batch(
                                connection, policy, parents, log_parents, logs
                            )
                        # Only count the batch after its transaction commits.
                        if not any(deleted.values()):
                            break
                        for key, value in deleted.items():
                            report[key] += value
                        report["committed_batches"] += 1
                        logger.info("Committed workflow retention batch: %s", deleted)
                        pause = min(
                            policy.batch_pause_ms / 1000,
                            max(0, deadline - time.monotonic()),
                        )
                        if pause:
                            time.sleep(pause)
        if not apply:
            for key in (
                "eligible_executions",
                "eligible_logs",
                "stored_results_bytes",
                "eligible_alert_associations",
                "eligible_incident_associations",
            ):
                report[key] = report[key] or 0
        report["completed"] = True
        report["stop_reason"] = "finished"
    except _BudgetExpired:
        report["stop_reason"] = "runtime_limit"
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None) or getattr(
            error.orig, "pgcode", None
        )
        if code != "57014":
            raise
        report["stop_reason"] = "query_timeout"
    return report
