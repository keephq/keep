#!/usr/bin/env python3
"""
scripts/cleanup_workflow_executions.py

PostgreSQL (and MySQL/SQLite) supported workflow execution and log retention cleanup.
Addresses #6942 (PostgreSQL TOAST/heap storage exhaustion on WorkflowExecution & WorkflowExecutionLog).

Supports:
- --retention-days: purge completed executions older than N days (default: 30)
- --batch-size: purge in bounded chunks to avoid lock contention & WAL spikes (default: 500)
- --dry-run: simulate count of executions and logs that would be purged without deleting
- --tenant-id: limit purge to a specific tenant (default: all tenants)
- --keep-failed: preserve failed/error executions for post-mortem debugging
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select, col

# Adjust path for keep imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keep.api.core.db import get_session
from keep.api.models.db.workflow import WorkflowExecution, WorkflowExecutionLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TERMINAL_SUCCESS_STATUSES = ["success", "passed"]
TERMINAL_FAILED_STATUSES = ["error", "timeout", "failed", "cancelled"]


def purge_workflow_executions(
    session: Session,
    retention_days: int = 30,
    batch_size: int = 500,
    dry_run: bool = False,
    tenant_id: str | None = None,
    keep_failed: bool = False,
) -> dict[str, int]:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    logger.info(f"Purge cutoff date: {cutoff_date.isoformat()} (retention: {retention_days} days)")

    terminal_statuses = list(TERMINAL_SUCCESS_STATUSES)
    if not keep_failed:
        terminal_statuses.extend(TERMINAL_FAILED_STATUSES)

    statement = select(WorkflowExecution.id).where(
        col(WorkflowExecution.started) < cutoff_date,
        col(WorkflowExecution.status).in_(terminal_statuses),
    )

    if tenant_id:
        statement = statement.where(WorkflowExecution.tenant_id == tenant_id)

    total_executions_purged = 0
    total_logs_purged = 0

    while True:
        batch_stmt = statement.limit(batch_size)
        execution_ids = session.exec(batch_stmt).all()

        if not execution_ids:
            break

        logger.info(f"Found {len(execution_ids)} executions to purge in current batch...")

        if dry_run:
            total_executions_purged += len(execution_ids)
            log_count_stmt = select(WorkflowExecutionLog.id).where(
                col(WorkflowExecutionLog.workflow_execution_id).in_(execution_ids)
            )
            logs_in_batch = len(session.exec(log_count_stmt).all())
            total_logs_purged += logs_in_batch
            break

        # Delete dependent WorkflowExecutionLog entries first
        del_logs_stmt = select(WorkflowExecutionLog).where(
            col(WorkflowExecutionLog.workflow_execution_id).in_(execution_ids)
        )
        logs = session.exec(del_logs_stmt).all()
        for log in logs:
            session.delete(log)
        total_logs_purged += len(logs)

        # Delete WorkflowExecution entries
        del_exec_stmt = select(WorkflowExecution).where(
            col(WorkflowExecution.id).in_(execution_ids)
        )
        execs = session.exec(del_exec_stmt).all()
        for ex in execs:
            session.delete(ex)
        total_executions_purged += len(execs)

        session.commit()
        logger.info(f"Purged batch: {len(execs)} executions, {len(logs)} logs.")

    summary = {
        "executions_purged": total_executions_purged,
        "logs_purged": total_logs_purged,
        "dry_run": dry_run,
    }
    logger.info(f"Cleanup summary: {summary}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Purge historical Keep workflow executions and logs.")
    parser.add_argument("--retention-days", type=int, default=30, help="Purge executions older than N days.")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for deletion chunks.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without deleting records.")
    parser.add_argument("--tenant-id", type=str, default=None, help="Filter by specific tenant.")
    parser.add_argument("--keep-failed", action="store_true", help="Preserve failed/timeout executions.")
    args = parser.parse_args()

    with get_session() as session:
        purge_workflow_executions(
            session=session,
            retention_days=args.retention_days,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            tenant_id=args.tenant_id,
            keep_failed=args.keep_failed,
        )


if __name__ == "__main__":
    main()
