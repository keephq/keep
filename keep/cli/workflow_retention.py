#!/usr/bin/env python3
"""Preview/apply bounded PostgreSQL workflow-history retention (issue #6942)."""

import argparse
import json
import logging
import sys

from keep.api.core.workflow_retention import RetentionPolicy, run_retention


def _get_engine():
    # Reuse Keep's configured engine without treating get_session() as a context manager.
    # Import only after validating arguments; --help/invalid arguments never open the DB.
    from keep.api.core.db import engine

    return engine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--tenant-id")
    scope.add_argument("--all-tenants", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Delete eligible history; default is dry-run",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit read-only preview (the default)",
    )
    parser.add_argument(
        "--retention-days",
        "--success-retention-days",
        dest="success_days",
        type=int,
        default=30,
    )
    failures = parser.add_mutually_exclusive_group()
    failures.add_argument(
        "--failure-retention-days", dest="failure_days", type=int, default=30
    )
    failures.add_argument("--keep-failed", action="store_true")
    parser.add_argument(
        "--success-log-retention-days", dest="success_log_days", type=int
    )
    parser.add_argument("--keep-successes", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--log-batch-size", type=int, default=5000)
    parser.add_argument("--batch-pause-ms", type=int, default=200)
    parser.add_argument("--max-runtime-seconds", type=int, default=600)
    parser.add_argument("--statement-timeout-ms", type=int, default=15000)
    parser.add_argument("--lock-timeout-ms", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        policy = RetentionPolicy(
            success_days=args.success_days,
            failure_days=None if args.keep_failed else args.failure_days,
            success_log_days=args.success_log_days,
            keep_successes=args.keep_successes,
            batch_size=args.batch_size,
            log_batch_size=args.log_batch_size,
            batch_pause_ms=args.batch_pause_ms,
            max_runtime_seconds=args.max_runtime_seconds,
            statement_timeout_ms=args.statement_timeout_ms,
            lock_timeout_ms=args.lock_timeout_ms,
        )
        if args.tenant_id is not None and not args.tenant_id.strip():
            raise ValueError("tenant-id cannot be empty")
    except ValueError as error:
        parser.error(str(error))
    try:
        report = run_retention(
            _get_engine(),
            policy,
            tenant_id=args.tenant_id,
            all_tenants=args.all_tenants,
            apply=args.apply,
        )
    except ValueError as error:
        parser.exit(1, f"Retention preflight failed: {error}\n")
    except Exception as error:
        # Driver exceptions can embed connection credentials, SQL, or row contents.
        parser.exit(
            1,
            f"Retention failed ({type(error).__name__}); check database health and permissions\n",
        )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["completed"] else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
