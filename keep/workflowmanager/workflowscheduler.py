import asyncio
import logging
import threading
import time
import typing

from keep.api.core.db import (
    create_workflow_execution,
    finish_workflow_execution,
    get_session,
    get_workflows_that_should_run,
)
from keep.api.models.db.workflow import WorkflowExecution
from keep.contextmanager.contextmanager import ContextManager
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowstore import WorkflowStore


class WorkflowScheduler:
    def __init__(self, workflow_manager):
        self.logger = logging.getLogger(__name__)
        self.threads = []
        self.workflow_manager = workflow_manager
        self.workflow_store = WorkflowStore()
        # all workflows that needs to be run due to alert event
        self.workflows_to_run = []
        self._stop = False

    async def start(self):
        self.logger.info("Starting workflows scheduler")
        thread = threading.Thread(target=self._start)
        thread.start()
        self.threads.append(thread)
        self.logger.info("Workflows scheduler started")

    def _handle_interval_workflows(self):
        workflows = []
        try:
            # get all workflows that should run due to interval
            workflows = get_workflows_that_should_run()
        except Exception as e:
            self.logger.error(f"Error getting workflows that should run: {e}")
            pass
        for workflow in workflows:
            self.logger.info("Running workflow on background")
            try:
                workflow_execution_id = workflow.get("workflow_execution_id")
                tenant_id = workflow.get("tenant_id")
                workflow_id = workflow.get("workflow_id")
                workflow = self.workflow_store.get_workflow(tenant_id, workflow_id)
            except Exception as e:
                self.logger.error(f"Error getting workflow: {e}")
                finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    execution_id=workflow_execution_id,
                    status="error",
                    error=f"Error getting workflow: {e}",
                )
                continue
            thread = threading.Thread(
                target=self._run_workflow,
                args=[tenant_id, workflow_id, workflow, workflow_execution_id],
            )
            thread.start()
            self.threads.append(thread)

    def _run_workflow(
        self,
        tenant_id,
        workflow_id,
        workflow: Workflow,
        workflow_execution_id: str,
        event_context=None,
    ):
        self.logger.info(f"Running workflow {workflow.workflow_id}...")
        try:
            # set the event context, e.g. the event that triggered the workflow
            workflow.context_manager.set_event_context(event_context)
            self.workflow_manager._run_workflow(workflow)
        except Exception as e:
            self.logger.exception(f"Failed to run workflow {workflow.workflow_id}...")
            finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                execution_id=workflow_execution_id,
                status="error",
                error=str(e),
            )

        finish_workflow_execution(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=workflow_execution_id,
            status="success",
            error=None,
        )
        self.logger.info(f"Workflow {workflow.workflow_id} ran")

    def _handle_event_workflows(self):
        # take out all items from the workflows to run and run them, also, clean the self.workflows_to_run list
        workflows_to_run, self.workflows_to_run = self.workflows_to_run, []
        for workflow_to_run in workflows_to_run:
            self.logger.info("Running event workflow on background")
            workflow = workflow_to_run.get("workflow")
            workflow_id = workflow_to_run.get("workflow_id")
            tenant_id = workflow_to_run.get("tenant_id")
            event = workflow_to_run.get("event")
            triggered_by = workflow_to_run.get("triggered_by")
            if triggered_by == "manual":
                triggered_by_user = workflow_to_run.get("triggered_by_user")
                triggered_by = f"manually by {triggered_by_user}"
            else:
                triggered_by = (f"type:alert name:{event.name} id:{event.id}",)
            workflow_execution_id = create_workflow_execution(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                triggered_by=triggered_by,
            )
            thread = threading.Thread(
                target=self._run_workflow,
                args=[tenant_id, workflow_id, workflow, workflow_execution_id, event],
            )
            thread.start()
            self.threads.append(thread)

    def _start(self):
        self.logger.info("Starting workflows scheduler")
        while not self._stop:
            # get all workflows that should run now
            self.logger.info("Getting workflows that should run...")
            self._handle_interval_workflows()
            self._handle_event_workflows()
            self.logger.info("Sleeping until next iteration")
            time.sleep(1)
        self.logger.info("Workflows scheduler stopped")

    def run_workflows(self, workflows: typing.List[Workflow]):
        for workflow in workflows:
            thread = threading.Thread(
                target=self._run_workflows_with_interval,
                args=[workflow],
                daemon=True,
            )
            thread.start()
            self.threads.append(thread)
        # as long as the stop flag is not set, sleep
        while not self._stop:
            time.sleep(1)

    def stop(self):
        self.logger.info("Stopping scheduled workflows")
        self._stop = True
        # Now wait for the threads to finish
        for thread in self.threads:
            thread.join()
        self.logger.info("Scheduled workflows stopped")

    def _run_workflows_with_interval(
        self,
        workflow: Workflow,
    ):
        """Simple scheduling of workflows with interval

        TODO: Use https://github.com/agronholm/apscheduler

        Args:
            workflow (Workflow): The workflow to run.
        """
        while True and not self._stop:
            self.logger.info(f"Running workflow {workflow.workflow_id}...")
            try:
                self.workflow_manager._run_workflow(workflow)
            except Exception as e:
                self.logger.exception(
                    f"Failed to run workflow {workflow.workflow_id}..."
                )
            self.logger.info(f"Workflow {workflow.workflow_id} ran")
            if workflow.workflow_interval > 0:
                self.logger.info(
                    f"Sleeping for {workflow.workflow_interval} seconds..."
                )
                time.sleep(workflow.workflow_interval)
            else:
                self.logger.info("Workflow will not run again")
                break
