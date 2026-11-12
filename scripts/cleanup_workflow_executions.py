#!/usr/bin/env python3
"""
scripts/cleanup_workflow_executions.py

Database-safe workflow execution and log retention cleanup for Keep (#6942).
Addresses PostgreSQL TOAST/heap storage growth on `workflowexecution` (large JSON `results`)
and `workflowexecutionlog`.

Key safety & operational properties:
- Uses `get_session_sync()` context management for synchronous CLI execution.
- Validates `retention_days`, `failed_retention_days`, `batch_size`, `log_batch_size`, and
  `max_runtime_seconds` before any database access.
- Selects only `WorkflowExecution.id` and deletes via bulk SQL `DELETE` statements so large
  `WorkflowExecution.results` TOAST payloads and full `WorkflowExecutionLog` objects are
  never loaded into Python memory.
- Deletes dependent rows in `WorkflowExecutionLog` (bounded by `log_batch_size`),
  `WorkflowToAlertExecution`, and `WorkflowToIncidentExecution` before deleting parent
  `WorkflowExecution` rows, preserving `Alert` and `Incident` records.
- In `--dry-run` mode (CLI default unless `--apply` is specified), reports complete aggregate
  counts across the entire eligible dataset without truncating at the first batch.
- Includes `providers_not_configured` among terminal failure statuses and never assumes
  `WorkflowExecution.is_running` is a boolean (Keep assigns random positive integers on finish).
- Optional `--preserve-latest-per-workflow` retains the latest non-test successful execution
  and the scheduler-relevant last completed execution per `(tenant_id, workflow_id)`.

Operational & PostgreSQL Prerequisites:
1. Index prerequisite: On large installations where `workflowexecutionlog` lacks an index on
   `workflow_execution_id`, build it concurrently before running batched deletes:
   `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflowexecutionlog_workflow_execution_id ON workflowexecutionlog (workflow_execution_id);`
   This script deliberately does not create indexes automatically.
2. Disk-space expectations: Standard `DELETE` + `VACUUM` marks dead tuples/TOAST pages reusable
   within PostgreSQL (`pg_freespace`) rather than immediately shrinking OS filesystem usage.
   Reclaiming OS disk space requires a separately planned `VACUUM FULL` or `pg_repack` maintenance window.
3. Checkpoint behavior: Keep's `get_previous_execution_id` and `get_last_workflow_execution_by_workflow_id`
   bound history lookups to 1 day (`timedelta(days=1)`), while `get_last_completed_execution` inspects the
   latest non-test execution (`status IN ('success', 'error', 'providers_not_configured')`). Enabling
   `--preserve-latest-per-workflow` retains both the latest non-test success and the latest scheduler-relevant
   completed record per workflow regardless of age.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, delete, func, or_
from sqlmodel import Session, col, select

# Adjust path for keep imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keep.api.core.db import get_session_sync
from keep.api.models.db.workflow import (
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowToAlertExecution,
    WorkflowToIncidentExecution,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TERMINAL_SUCCESS_STATUSES = ("success", "passed")
TERMINAL_FAILED_STATUSES = (
    "error",
    "timeout",
    "failed",
    "cancelled",
    "providers_not_configured",
)
SCHEDULER_COMPLETED_STATUSES = ("success", "error", "providers_not_configured")


def _validate_parameters(
    retention_days: int,
    batch_size: int,
    failed_retention_days: int | None = None,
    log_batch_size: int = 5000,
    max_runtime_seconds: float | None = None,
) -> None:
    if not isinstance(retention_days, int) or isinstance(retention_days, bool) or retention_days < 1:
        raise ValueError(f"retention_days must be an integer >= 1 (got {retention_days!r})")
    if failed_retention_days is not None and (
        not isinstance(failed_retention_days, int)
        or isinstance(failed_retention_days, bool)
        or failed_retention_days < 1
    ):
        raise ValueError(
            f"failed_retention_days must be an integer >= 1 when specified (got {failed_retention_days!r})"
        )
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError(f"batch_size must be an integer >= 1 (got {batch_size!r})")
    if not isinstance(log_batch_size, int) or isinstance(log_batch_size, bool) or log_batch_size < 1:
        raise ValueError(f"log_batch_size must be an integer >= 1 (got {log_batch_size!r})")
    if max_runtime_seconds is not None and max_runtime_seconds <= 0:
        raise ValueError(f"max_runtime_seconds must be > 0 when specified (got {max_runtime_seconds!r})")


def get_protected_execution_ids(
    session: Session,
    tenant_id: str | None = None,
) -> set[str]:
    """
    Identify execution IDs that should be preserved per (tenant_id, workflow_id):
    1. Latest non-test successful execution (`status IN TERMINAL_SUCCESS_STATUSES`).
    2. Scheduler-relevant last completed non-test execution (`status IN SCHEDULER_COMPLETED_STATUSES`,
       ordered by `execution_number DESC, started DESC`).
    """
    protected_ids: set[str] = set()

    base_filters = [col(WorkflowExecution.is_test_run) == False]  # noqa: E712
    if tenant_id:
        base_filters.append(WorkflowExecution.tenant_id == tenant_id)

    workflows_stmt = (
        select(WorkflowExecution.tenant_id, WorkflowExecution.workflow_id)
        .where(*base_filters)
        .distinct()
    )
    tenant_workflows = session.exec(workflows_stmt).all()

    for t_id, wf_id in tenant_workflows:
        # 1. Latest non-test success
        latest_success_id = session.exec(
            select(WorkflowExecution.id)
            .where(
                WorkflowExecution.tenant_id == t_id,
                WorkflowExecution.workflow_id == wf_id,
                col(WorkflowExecution.is_test_run) == False,  # noqa: E712
                col(WorkflowExecution.status).in_(TERMINAL_SUCCESS_STATUSES),
            )
            .order_by(
                col(WorkflowExecution.started).desc(),
                col(WorkflowExecution.execution_number).desc(),
            )
            .limit(1)
        ).first()
        if latest_success_id:
            protected_ids.add(latest_success_id)

        # 2. Latest scheduler-relevant completed record
        latest_completed_id = session.exec(
            select(WorkflowExecution.id)
            .where(
                WorkflowExecution.tenant_id == t_id,
                WorkflowExecution.workflow_id == wf_id,
                col(WorkflowExecution.is_test_run) == False,  # noqa: E712
                col(WorkflowExecution.status).in_(SCHEDULER_COMPLETED_STATUSES),
            )
            .order_by(
                col(WorkflowExecution.execution_number).desc(),
                col(WorkflowExecution.started).desc(),
            )
            .limit(1)
        ).first()
        if latest_completed_id:
            protected_ids.add(latest_completed_id)

    return protected_ids


def _build_eligible_ids_statement(
    now: datetime,
    retention_days: int,
    failed_retention_days: int | None,
    tenant_id: str | None,
    keep_failed: bool,
    protected_ids: set[str],
):
    success_cutoff = now - timedelta(days=retention_days)
    effective_failed_days = (
        failed_retention_days if failed_retention_days is not None else retention_days
    )
    failed_cutoff = now - timedelta(days=effective_failed_days)

    if keep_failed:
        status_time_condition = and_(
            col(WorkflowExecution.status).in_(TERMINAL_SUCCESS_STATUSES),
            col(WorkflowExecution.started) < success_cutoff,
        )
    elif failed_retention_days is not None and failed_retention_days != retention_days:
        status_time_condition = or_(
            and_(
                col(WorkflowExecution.status).in_(TERMINAL_SUCCESS_STATUSES),
                col(WorkflowExecution.started) < success_cutoff,
            ),
            and_(
                col(WorkflowExecution.status).in_(TERMINAL_FAILED_STATUSES),
                col(WorkflowExecution.started) < failed_cutoff,
            ),
        )
    else:
        all_terminal = list(TERMINAL_SUCCESS_STATUSES) + list(TERMINAL_FAILED_STATUSES)
        status_time_condition = and_(
            col(WorkflowExecution.status).in_(all_terminal),
            col(WorkflowExecution.started) < success_cutoff,
        )

    stmt = select(WorkflowExecution.id).where(status_time_condition)

    if tenant_id:
        stmt = stmt.where(WorkflowExecution.tenant_id == tenant_id)

    if protected_ids:
        stmt = stmt.where(col(WorkflowExecution.id).notin_(protected_ids))

    return stmt.order_by(col(WorkflowExecution.started).asc(), col(WorkflowExecution.id).asc())


def purge_workflow_executions(
    session: Session,
    retention_days: int = 30,
    batch_size: int = 500,
    dry_run: bool = False,
    tenant_id: str | None = None,
    keep_failed: bool = False,
    failed_retention_days: int | None = None,
    log_batch_size: int = 5000,
    preserve_latest_per_workflow: bool = False,
    max_runtime_seconds: float | None = None,
) -> dict[str, int | bool]:
    _validate_parameters(
        retention_days=retention_days,
        batch_size=batch_size,
        failed_retention_days=failed_retention_days,
        log_batch_size=log_batch_size,
        max_runtime_seconds=max_runtime_seconds,
    )

    now = datetime.now(timezone.utc)
    start_monotonic = time.monotonic()

    protected_ids: set[str] = set()
    if preserve_latest_per_workflow:
        protected_ids = get_protected_execution_ids(session=session, tenant_id=tenant_id)

    statement = _build_eligible_ids_statement(
        now=now,
        retention_days=retention_days,
        failed_retention_days=failed_retention_days,
        tenant_id=tenant_id,
        keep_failed=keep_failed,
        protected_ids=protected_ids,
    )

    if dry_run:
        eligible_subq = statement.subquery()
        eligible_id_select = select(eligible_subq.c.id)

        total_executions = int(
            session.exec(select(func.count()).select_from(eligible_subq)).one() or 0
        )
        total_logs = int(
            session.exec(
                select(func.count(WorkflowExecutionLog.id)).where(
                    col(WorkflowExecutionLog.workflow_execution_id).in_(eligible_id_select)
                )
            ).one()
            or 0
        )
        total_alert_assocs = int(
            session.exec(
                select(func.count(WorkflowToAlertExecution.id)).where(
                    col(WorkflowToAlertExecution.workflow_execution_id).in_(eligible_id_select)
                )
            ).one()
            or 0
        )
        total_incident_assocs = int(
            session.exec(
                select(func.count(WorkflowToIncidentExecution.id)).where(
                    col(WorkflowToIncidentExecution.workflow_execution_id).in_(
                        eligible_id_select
                    )
                )
            ).one()
            or 0
        )

        summary: dict[str, int | bool] = {
            "executions_purged": total_executions,
            "logs_purged": total_logs,
            "alert_associations_purged": total_alert_assocs,
            "incident_associations_purged": total_incident_assocs,
            "batches_completed": 0,
            "dry_run": True,
            "time_limit_reached": False,
        }
        logger.info(f"Dry-run summary (full eligible scope): {summary}")
        return summary

    total_executions_purged = 0
    total_logs_purged = 0
    total_alert_assocs_purged = 0
    total_incident_assocs_purged = 0
    batches_completed = 0
    time_limit_reached = False

    while True:
        if (
            max_runtime_seconds is not None
            and (time.monotonic() - start_monotonic) >= max_runtime_seconds
        ):
            time_limit_reached = True
            logger.info("Reached max_runtime_seconds limit; stopping cleanly after committed batches.")
            break

        execution_ids = list(session.exec(statement.limit(batch_size)).all())
        if not execution_ids:
            break

        logger.info(f"Found {len(execution_ids)} executions to purge in current batch...")

        try:
            # 1. Delete dependent WorkflowExecutionLog entries in bounded chunks
            batch_logs_deleted = 0
            while True:
                log_ids = list(
                    session.exec(
                        select(WorkflowExecutionLog.id)
                        .where(
                            col(WorkflowExecutionLog.workflow_execution_id).in_(execution_ids)
                        )
                        .limit(log_batch_size)
                    ).all()
                )
                if not log_ids:
                    break
                session.exec(
                    delete(WorkflowExecutionLog).where(
                        col(WorkflowExecutionLog.id).in_(log_ids)
                    )
                )
                batch_logs_deleted += len(log_ids)

            # 2. Delete WorkflowToAlertExecution associations (preserving Alert rows)
            alert_res = session.exec(
                delete(WorkflowToAlertExecution).where(
                    col(WorkflowToAlertExecution.workflow_execution_id).in_(execution_ids)
                )
            )
            batch_alert_assocs = int(getattr(alert_res, "rowcount", 0) or 0)

            # 3. Delete WorkflowToIncidentExecution associations (preserving Incident rows)
            incident_res = session.exec(
                delete(WorkflowToIncidentExecution).where(
                    col(WorkflowToIncidentExecution.workflow_execution_id).in_(execution_ids)
                )
            )
            batch_incident_assocs = int(getattr(incident_res, "rowcount", 0) or 0)

            # 4. Delete parent WorkflowExecution rows by ID without loading `results` JSON
            exec_res = session.exec(
                delete(WorkflowExecution).where(
                    col(WorkflowExecution.id).in_(execution_ids)
                )
            )
            batch_execs_deleted = int(
                getattr(exec_res, "rowcount", len(execution_ids)) or len(execution_ids)
            )

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Error purging batch; transaction rolled back.")
            raise

        total_executions_purged += batch_execs_deleted
        total_logs_purged += batch_logs_deleted
        total_alert_assocs_purged += batch_alert_assocs
        total_incident_assocs_purged += batch_incident_assocs
        batches_completed += 1

        logger.info(
            f"Purged batch #{batches_completed}: {batch_execs_deleted} executions, "
            f"{batch_logs_deleted} logs, {batch_alert_assocs} alert links, "
            f"{batch_incident_assocs} incident links."
        )

    summary = {
        "executions_purged": total_executions_purged,
        "logs_purged": total_logs_purged,
        "alert_associations_purged": total_alert_assocs_purged,
        "incident_associations_purged": total_incident_assocs_purged,
        "batches_completed": batches_completed,
        "dry_run": False,
        "time_limit_reached": time_limit_reached,
    }
    logger.info(f"Cleanup summary: {summary}")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Purge historical Keep workflow executions and logs safely."
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Purge completed executions older than N days (default: 30, must be >= 1).",
    )
    parser.add_argument(
        "--failed-retention-days",
        type=int,
        default=None,
        help="Optional separate retention window (in days, >= 1) for failed/error executions.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of workflow executions to purge per transaction batch (default: 500).",
    )
    parser.add_argument(
        "--log-batch-size",
        type=int,
        default=5000,
        help="Maximum WorkflowExecutionLog rows deleted per statement chunk (default: 5000).",
    )
    parser.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime in seconds before stopping cleanly between batches.",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
         help="Report full eligible counts without deleting records (default mode unless --apply is set).",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Execute actual deletion batches in the database.",
    )

    tenant_group = parser.add_mutually_exclusive_group(required=True)
    tenant_group.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Filter cleanup to a specific tenant ID.",
    )
    tenant_group.add_argument(
        "--all-tenants",
        action="store_true",
        help="Explicitly run cleanup across all tenants.",
    )

    parser.add_argument(
        "--keep-failed",
        action="store_true",
        help="Preserve failed/timeout/providers_not_configured executions.",
    )
    parser.add_argument(
        "--preserve-latest-per-workflow",
        action="store_true",
        help="Preserve the latest non-test success and scheduler-relevant completed execution per workflow.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> dict[str, int | bool]:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Validate parameters before opening a database session
    _validate_parameters(
        retention_days=args.retention_days,
        batch_size=args.batch_size,
        failed_retention_days=args.failed_retention_days,
        log_batch_size=args.log_batch_size,
        max_runtime_seconds=args.max_runtime_seconds,
    )

    # Default to dry-run unless --apply is explicitly provided
    effective_dry_run = True if not args.apply else False
    if args.dry_run:
        effective_dry_run = True

    effective_tenant_id = None if args.all_tenants else args.tenant_id

    with get_session_sync() as session:
        return purge_workflow_executions(
            session=session,
            retention_days=args.retention_days,
            batch_size=args.batch_size,
            dry_run=effective_dry_run,
            tenant_id=effective_tenant_id,
            keep_failed=args.keep_failed,
            failed_retention_days=args.failed_retention_days,
            log_batch_size=args.log_batch_size,
            preserve_latest_per_workflow=args.preserve_latest_per_workflow,
            max_runtime_seconds=args.max_runtime_seconds,
        )


if __name__ == "__main__":
    main()
