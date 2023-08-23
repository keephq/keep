import logging
import os
import time
import typing

from keep.parser.parser import Parser
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowscheduler import WorkflowScheduler
from keep.workflowmanager.workflowstore import WorkflowStore


class WorkflowManager:
    @staticmethod
    def get_instance() -> "WorkflowManager":
        if not hasattr(WorkflowManager, "_instance"):
            WorkflowManager._instance = WorkflowManager()
        return WorkflowManager._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scheduler = WorkflowScheduler(self)
        self.workflow_store = WorkflowStore()

    async def start(self):
        """Runs the workflow manager in server mode"""
        await self.scheduler.start()

    def insert_events(self, tenant_id, events: typing.List[dict]):
        workflows_that_should_be_run = []
        for event in events:
            all_workflow_models = self.workflow_store.get_all_workflows(tenant_id)
            for workflow_model in all_workflow_models:
                try:
                    # get the actual workflow that can be triggered
                    workflow = self.workflow_store.get_workflow(
                        tenant_id, workflow_model.id
                    )
                # the provider is not configured, hence the workflow cannot be triggered
                # todo - handle it better
                # todo2 - handle if more than one provider is not configured
                except ProviderConfigurationException as e:
                    self.logger.error(
                        f"Workflow have a provider that is not configured: {e}"
                    )
                    continue
                except Exception as e:
                    # TODO: how to handle workflows that aren't properly parsed/configured?
                    self.logger.error(f"Error getting workflow: {e}")
                    continue
                for trigger in workflow.workflow_triggers:
                    # TODO: handle it better
                    if not trigger.get("type") == "alert":
                        continue
                    for filter in trigger.get("filters", []):
                        # TODO: more sophisticated filtering/attributes/nested, etc
                        filter_key = filter.get("key")
                        filter_val = filter.get("value")
                        if not getattr(event, filter_key, None):
                            self.logger.warning(
                                "Failed to run filter, skipping the event. Probably misconfigured workflow."
                            )
                            continue
                        # if its list, check if the filter is in the list
                        if type(getattr(event, filter_key)) == list:
                            if filter_val not in getattr(event, filter_key):
                                self.logger.debug(
                                    "Filter didn't match, skipping",
                                    extra={
                                        "filter_key": filter_key,
                                        "filter_val": filter_val,
                                        "event": event,
                                    },
                                )
                                continue
                        # elif the filter is string/int/float, compare them:
                        elif type(getattr(event, filter_key, None)) in [
                            int,
                            str,
                            float,
                        ]:
                            if not getattr(event, filter_key) == filter_val:
                                self.logger.debug(
                                    "Filter didn't match, skipping",
                                    extra={
                                        "filter_key": filter_key,
                                        "filter_val": filter_val,
                                        "event": event,
                                    },
                                )
                                continue
                        # other types currently does not supported
                        else:
                            self.logger.warning(
                                "Could not run the filter on unsupported type, skipping the event. Probably misconfigured workflow."
                            )
                            continue

                    # if we got here, it means the event should trigger the workflow
                    self.scheduler.workflows_to_run.append(
                        {
                            "workflow": workflow,
                            "workflow_id": workflow_model.id,
                            "tenant_id": tenant_id,
                            "event": event,
                        }
                    )

    # TODO should be fixed to support the usual CLI
    def run(self, workflows: list[Workflow]):
        """
        Run list of workflows.

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
