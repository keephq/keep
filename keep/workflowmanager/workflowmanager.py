import logging
import os
import threading
import time
import typing

from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowscheduler import WorkflowScheduler


# TODO - workflowmanager should be sync to db
#        things such as executions and intervals should be also in db
class WorkflowManager:
    def __init__(self, interval: int = 0):
        self.logger = logging.getLogger(__name__)
        self.scheduler = WorkflowScheduler(self)
        self.context_manager = ContextManager.get_instance()
        self.default_interval = interval
        self.scheduler_mode = False

    def stop(self):
        if self.scheduler_mode:
            self.logger.info("Stopping workflow manager")
            self.context_manager.dump()
            self.scheduler.stop()
            self.logger.info("Workflow manager stopped")
        else:
            pass

    def run(self, workflows: list[Workflow]):
        """
        Run workflows from a file or directory.

        Args:
            workflow (str): Either an workflow yaml or a directory containing workflow yamls or a list of URLs to get the workflows from.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        self.logger.info(f"Running workflow(s)")
        workflows_errors = []
        # If at least one workflow has an interval, run workflows using the scheduler,
        #   otherwise, just run it
        if self.default_interval or any(
            [Workflow.workflow_interval for Workflow in workflows]
        ):
            # running workglows in scheduler mode
            self.logger.info(
                "Found at least one workflow with an interval, running in scheduler mode"
            )
            self.scheduler_mode = True
            # if the workflows doesn't have an interval, set the default interval
            for workflow in workflows:
                workflow.workflow_interval = (
                    workflow.workflow_interval or self.default_interval
                )
            # This will halt until KeyboardInterrupt
            self.scheduler.run_workflows(workflows)
            self.logger.info("Workflow(s) scheduled")
        else:
            # running workflows in the regular mode
            workflows_errors = self._run_workflows(workflows)

        return workflows_errors

    def _run_workflow(self, workflow: Workflow):
        self.logger.info(f"Running workflow {workflow.workflow_id}")
        errors = []
        try:
            errors = workflow.run()
        except Exception as e:
            self.logger.error(
                f"Error running workflow {workflow.workflow_id}", extra={"exception": e}
            )
            if workflow.on_failure:
                self.logger.info(
                    f"Running on_failure action for workflow {workflow.workflow_id}"
                )
                # Adding the exception message to the provider context so it'll be available for the action
                message = f"Workflow `{workflow.workflow_id}` failed with exception: `{str(e)}`"
                workflow.on_failure.provider_parameters = {"message": message}
                workflow.on_failure.run()
            raise
        if any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
        else:
            self.logger.info(f"Workflow {workflow.workflow_id} ran successfully")
        return errors

    def _run_workflows(self, workflows: typing.List[Workflow]):
        workflows_errors = []
        for workflow in workflows:
            try:
                errors = self._run_workflow(workflow)
                workflows_errors.append(errors)
            except Exception as e:
                self.logger.error(
                    f"Error running workflow {workflow.workflow_id}",
                    extra={"exception": e},
                )
                raise

        return workflows_errors
