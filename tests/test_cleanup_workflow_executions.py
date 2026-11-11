import unittest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine
from keep.api.models.db.workflow import WorkflowExecution, WorkflowExecutionLog
from scripts.cleanup_workflow_executions import purge_workflow_executions


class TestCleanupWorkflowExecutions(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        fresh_time = datetime.now(timezone.utc) - timedelta(days=5)

        # 1. Old successful execution
        ex1 = WorkflowExecution(
            id="exec-old-success",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            status="success",
            started=old_time,
            execution_number=1,
        )
        self.session.add(ex1)
        self.session.add(WorkflowExecutionLog(
            workflow_execution_id="exec-old-success",
            timestamp=old_time,
            message="Step completed",
            context={"step": 1},
        ))

        # 2. Old error execution
        ex2 = WorkflowExecution(
            id="exec-old-error",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            status="error",
            started=old_time,
            execution_number=2,
        )
        self.session.add(ex2)
        self.session.add(WorkflowExecutionLog(
            workflow_execution_id="exec-old-error",
            timestamp=old_time,
            message="Step failed",
            context={"step": 2},
        ))

        # 3. Old running/in-progress execution (must NEVER be purged)
        ex3 = WorkflowExecution(
            id="exec-old-running",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            status="in_progress",
            started=old_time,
            execution_number=3,
        )
        self.session.add(ex3)

        # 4. Fresh successful execution (< 30 days)
        ex4 = WorkflowExecution(
            id="exec-fresh-success",
            workflow_id="wf-1",
            tenant_id="tenant-a",
            status="success",
            started=fresh_time,
            execution_number=4,
        )
        self.session.add(ex4)

        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_dry_run_does_not_delete(self):
        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=True,
        )
        self.assertEqual(res["executions_purged"], 2)
        self.assertEqual(res["logs_purged"], 2)

        rem_execs = self.session.query(WorkflowExecution).count()
        self.assertEqual(rem_execs, 4)

    def test_purge_removes_old_terminal_records(self):
        res = purge_workflow_executions(
            session=self.session,
            retention_days=30,
            dry_run=False,
        )
        self.assertEqual(res["executions_purged"], 2)
        self.assertEqual(res["logs_purged"], 2)

        remaining_ids = [e.id for e in self.session.query(WorkflowExecution).all()]
        self.assertIn("exec-old-running", remaining_ids)
        self.assertIn("exec-fresh-success", remaining_ids)
        self.assertNotIn("exec-old-success", remaining_ids)
        self.assertNotIn("exec-old-error", remaining_ids)

        remaining_logs = self.session.query(WorkflowExecutionLog).count()
        self.assertEqual(remaining_logs, 0)

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


if __name__ == "__main__":
    unittest.main()
