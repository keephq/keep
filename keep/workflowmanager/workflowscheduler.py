import logging
import threading
import time
import typing

from keep.workflowmanager.workflow import Workflow


class WorkflowScheduler:
    def __init__(self, workflow_manager):
        self.logger = logging.getLogger(__name__)
        self.threads = []
        self.workflow_manager = workflow_manager
        self._stop = False

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
                self.logger.exception(f"Failed to run alert {workflow.alert_id}...")
            self.logger.info(f"Alert {workflow.alert_id} ran")
            if workflow.alert_interval > 0:
                self.logger.info(f"Sleeping for {workflow.alert_interval} seconds...")
                time.sleep(workflow.alert_interval)
            else:
                self.logger.info("Alert will not run again")
                break
