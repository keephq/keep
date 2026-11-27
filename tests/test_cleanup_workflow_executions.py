import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import event
from sqlmodel import Session, SQLModel, col, create_engine, select

from keep.api.models.db.tenant import Tenant
from keep.api.models.db.workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowToAlertExecution,
    WorkflowToIncidentExecution,
)
from scripts.cleanup_workflow_executions import (
    get_protected_execution_ids,
    main,
    purge_workflow_executions,
)


class TestCleanupWorkflowExecutions(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.session.add(Tenant(id="tenant-a", name="Tenant A"))
        self.session.add(
            Workflow(
                id="wf-1",
                tenant_id="tenant-a",
                name="wf-1",
                description="test workflow",
                created_by="unit-test",
                workflow_raw="{}",
            )
        )
        self.session.add(
            Workflow(
                id="wf-dormant",
                tenant_id="tenant-a",
                name="wf-dormant",
                description="dormant workflow",
                created_by="unit-test",
                workflow_raw="{}",
            )
        )
        self.session.commit()

        self.old_time = datetime.now(timezone.utc) - timedelta(days=45)
        self.fresh_time = datetime.now(timezone.utc) - timedelta(days=5)

        # 1. Old successful execution with logs + alert & incident associations
        ex1 = WorkflowExecution(
            id="exec-old-success",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            triggered_by="scheduler",
            status="success",
            started=self.old_time,
            execution_number=1,
            is_running=42123,  # Keep sets random positive int on finish
            is_test_run=False,
        )
        self.session.add(ex1)
        self.session.add(
            WorkflowExecutionLog(
                workflow_execution_id="exec-old-success",
                timestamp=self.old_time,
                message="Step completed",
                context={"step": 1},
            )
        )
        self.session.add(
            WorkflowToAlertExecution(
                workflow_execution_id="exec-old-success",
                alert_fingerprint="fp-alert-1",
                event_id="evt-1",
            )
        )
        self.session.add(
            WorkflowToIncidentExecution(
                workflow_execution_id="exec-old-success",
                incident_id="inc-1",
            )
        )

        # 2. Old error execution
        ex2 = WorkflowExecution(
            id="exec-old-error",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            triggered_by="alert",
            status="error",
            started=self.old_time,
            execution_number=2,
            is_running=98765,
            is_test_run=False,
        )
        self.session.add(ex2)
        self.session.add(
            WorkflowExecutionLog(
                workflow_execution_id="exec-old-error",
                timestamp=self.old_time,
                message="Step failed",
                context={"step": 2},
            )
        )

        # 3. Old running/in-progress execution (must NEVER be purged)
        ex3 = WorkflowExecution(
            id="exec-old-running",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            triggered_by="manual",
            status="in_progress",
            started=self.old_time,
            execution_number=3,
            is_running=1,
            is_test_run=False,
        )
        self.session.add(ex3)

        # 4. Fresh successful execution (< 30 days)
        ex4 = WorkflowExecution(
            id="exec-fresh-success",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            triggered_by="scheduler",
            status="success",
            started=self.fresh_time,
            execution_number=4,
            is_running=55111,
            is_test_run=False,
        )
        self.session.add(ex4)

        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_dry_run_does_not_delete_and_reports_associations(self):
        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=True,
        )
        self.assertEqual(res["executions_purged"], 2)
        self.assertEqual(res["logs_purged"], 2)
        self.assertEqual(res["alert_associations_purged"], 1)
        self.assertEqual(res["incident_associations_purged"], 1)

        rem_execs = self.session.query(WorkflowExecution).count()
        self.assertEqual(rem_execs, 4)

    def test_dry_run_reports_full_scope_across_multiple_batches(self):
        # Add 3 more old terminal executions -> 5 eligible total
        for i in range(3):
            eid = f"exec-extra-{i}"
            self.session.add(
                WorkflowExecution(
                    id=eid,
                    workflow_id="wf-1",
                    tenant_id="tenant-a",
                    triggered_by="scheduler",
                    status="providers_not_configured" if i == 0 else "success",
                    started=self.old_time - timedelta(days=i + 1),
                    execution_number=10 + i,
                    is_running=100 + i,
                    is_test_run=False,
                )
            )
            self.session.add(
                WorkflowExecutionLog(
                    workflow_execution_id=eid,
                    timestamp=self.old_time,
                    message=f"Extra log {i}",
                    context={},
                )
            )
        self.session.commit()

        # With batch_size=2, dry-run must report all 5 eligible executions and 5 logs
        res_dry = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            batch_size=2,
            dry_run=True,
        )
        self.assertEqual(res_dry["executions_purged"], 5)
        self.assertEqual(res_dry["logs_purged"], 5)

        # Apply mode with batch_size=2 must iterate across 3 batches to purge all 5
        res_apply = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            batch_size=2,
            log_batch_size=1,
            dry_run=False,
        )
        self.assertEqual(res_apply["executions_purged"], 5)
        self.assertEqual(res_apply["logs_purged"], 5)
        self.assertEqual(res_apply["batches_completed"], 3)

    def test_purge_removes_old_terminal_records_and_associations(self):
        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=False,
        )
        self.assertEqual(res["executions_purged"], 2)
        self.assertEqual(res["logs_purged"], 2)
        self.assertEqual(res["alert_associations_purged"], 1)
        self.assertEqual(res["incident_associations_purged"], 1)

        remaining_ids = [e.id for e in self.session.query(WorkflowExecution).all()]
        self.assertIn("exec-old-running", remaining_ids)
        self.assertIn("exec-fresh-success", remaining_ids)
        self.assertNotIn("exec-old-success", remaining_ids)
        self.assertNotIn("exec-old-error", remaining_ids)

        self.assertEqual(self.session.query(WorkflowExecutionLog).count(), 0)
        self.assertEqual(self.session.query(WorkflowToAlertExecution).count(), 0)
        self.assertEqual(self.session.query(WorkflowToIncidentExecution).count(), 0)

    def test_keep_failed_preserves_errors(self):
        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=False,
            keep_failed=True,
        )
        self.assertEqual(res["executions_purged"], 1)

        remaining_ids = [e.id for e in self.session.query(WorkflowExecution).all()]
        self.assertIn("exec-old-error", remaining_ids)
        self.assertIn("exec-old-running", remaining_ids)
        self.assertIn("exec-fresh-success", remaining_ids)

    def test_invalid_retention_and_batch_size_rejected_before_db_access(self):
        for bad_retention in (-1, 0, False):
            with self.assertRaises(ValueError):
                purge_workflow_executions(
                    session=self.session,
                    retention_days=bad_retention,  # type: ignore[arg-type]
                    dry_run=False,
                )
        for bad_batch in (-5, 0):
            with self.assertRaises(ValueError):
                purge_workflow_executions(
                    session=self.session,
                    retention_days=30,
                    batch_size=bad_batch,
                    dry_run=False,
                )
        # Ensure fresh execution was untouched
        self.assertEqual(self.session.query(WorkflowExecution).count(), 4)

    def test_preserve_latest_per_workflow_protects_dormant_workflow_checkpoint(self):
        # Dormant workflow wf-dormant has only old executions (#1 at 60d, #2 at 50d)
        self.session.add(
            WorkflowExecution(
                id="dormant-1",
                workflow_id="wf-dormant",
                tenant_id="tenant-a",
                triggered_by="scheduler",
                status="success",
                started=datetime.now(timezone.utc) - timedelta(days=60),
                execution_number=1,
                is_running=111,
                is_test_run=False,
            )
        )
        self.session.add(
            WorkflowExecution(
                id="dormant-2-latest",
                workflow_id="wf-dormant",
                tenant_id="tenant-a",
                triggered_by="scheduler",
                status="success",
                started=datetime.now(timezone.utc) - timedelta(days=50),
                execution_number=2,
                is_running=222,
                is_test_run=False,
            )
        )
        self.session.commit()

        protected = get_protected_execution_ids(self.session, tenant_id="tenant-a")
        self.assertIn("dormant-2-latest", protected)
        self.assertNotIn("dormant-1", protected)

        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=False,
            preserve_latest_per_workflow=True,
        )
        # Purges exec-old-success, exec-old-error, and dormant-1 (3 total), keeping dormant-2-latest
        self.assertEqual(res["executions_purged"], 3)
        remaining_ids = [e.id for e in self.session.query(WorkflowExecution).all()]
        self.assertIn("dormant-2-latest", remaining_ids)
        self.assertNotIn("dormant-1", remaining_ids)

    def test_cli_main_uses_get_session_sync_and_defaults_to_dry_run(self):
        class _DummySessionCtx:
            def __init__(self, sess):
                self._sess = sess

            def __enter__(self):
                return self._sess

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        with patch(
            "scripts.cleanup_workflow_executions.get_session_sync",
            return_value=_DummySessionCtx(self.session),
        ):
            # Default CLI mode (without --apply) must be dry_run=True
            res_dry = main(["--retention-days", "30", "--tenant-id", "tenant-a"])
            self.assertTrue(res_dry["dry_run"])
            self.assertEqual(res_dry["executions_purged"], 2)
            self.assertEqual(self.session.query(WorkflowExecution).count(), 4)

            # Explicit --apply mode deletes the 2 eligible records
            res_apply = main(["--retention-days", "30", "--all-tenants", "--apply"])
            self.assertFalse(res_apply["dry_run"])
            self.assertEqual(res_apply["executions_purged"], 2)
            self.assertEqual(self.session.query(WorkflowExecution).count(), 2)


if __name__ == "__main__":
    unittest.main()
