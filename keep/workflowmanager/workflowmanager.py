import logging
import os
import re
import typing
import uuid

from keep.api.core.config import AuthenticationType
from keep.api.core.db import get_enrichment, save_workflow_results
from keep.api.models.alert import AlertDto
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowscheduler import WorkflowScheduler
from keep.workflowmanager.workflowstore import WorkflowStore


class WorkflowManager:
    # List of providers that are not allowed to be used in workflows in multi tenant mode.
    PREMIUM_PROVIDERS = ["bash", "python"]

    @staticmethod
    def get_instance() -> "WorkflowManager":
        if not hasattr(WorkflowManager, "_instance"):
            WorkflowManager._instance = WorkflowManager()
        return WorkflowManager._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scheduler = WorkflowScheduler(self)
        self.workflow_store = WorkflowStore()
        self.started = False

    async def start(self):
        """Runs the workflow manager in server mode"""
        if self.started:
            self.logger.info("Workflow manager already started")
            return
        await self.scheduler.start()
        self.started = True

    def stop(self):
        """Stops the workflow manager"""
        self.scheduler.stop()
        self.started = False

    def _apply_filter(self, filter_val, value):
        # if its a regex, apply it
        if filter_val.startswith('r"'):
            try:
                # remove the r" and the last "
                pattern = re.compile(filter_val[2:-1])
                return pattern.findall(value)
            except Exception as e:
                self.logger.error(
                    f"Error applying regex filter: {filter_val} on value: {value}",
                    extra={"exception": e},
                )
                return False
        else:
            return value == filter_val

    def insert_events(self, tenant_id, events: typing.List[AlertDto]):
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
                    self.logger.warn(
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
                    should_run = True
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
                        if isinstance(getattr(event, filter_key), list):
                            for val in getattr(event, filter_key):
                                # if one filter applies, it should run
                                if self._apply_filter(filter_val, val):
                                    should_run = True
                                    break
                                should_run = False
                        # elif the filter is string/int/float, compare them:
                        elif type(getattr(event, filter_key, None)) in [
                            int,
                            str,
                            float,
                        ]:
                            val = getattr(event, filter_key)
                            if not self._apply_filter(filter_val, val):
                                self.logger.debug(
                                    "Filter didn't match, skipping",
                                    extra={
                                        "filter_key": filter_key,
                                        "filter_val": filter_val,
                                        "event": event,
                                    },
                                )
                                should_run = False
                                break
                        # other types currently does not supported
                        else:
                            self.logger.warning(
                                "Could not run the filter on unsupported type, skipping the event. Probably misconfigured workflow."
                            )
                            should_run = False
                            break

                    # if we got here, it means the event should trigger the workflow
                    if should_run:
                        self.logger.info("Found a workflow to run")
                        event.trigger = "alert"
                        # prepare the alert with the enrichment
                        self.logger.info("Enriching alert")
                        alert_enrichment = get_enrichment(tenant_id, event.fingerprint)
                        if alert_enrichment:
                            for k, v in alert_enrichment.enrichments.items():
                                setattr(event, k, v)
                        self.logger.info("Alert enriched")
                        self.scheduler.workflows_to_run.append(
                            {
                                "workflow": workflow,
                                "workflow_id": workflow_model.id,
                                "tenant_id": tenant_id,
                                "triggered_by": "alert",
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
        self.logger.info("Running workflow(s)")
        workflows_errors = []
        # If at least one workflow has an interval, run workflows using the scheduler,
        #   otherwise, just run it
        if any([Workflow.workflow_interval for Workflow in workflows]):
            # running workglows in scheduler mode
            self.logger.info(
                "Found at least one workflow with an interval, running in scheduler mode"
            )
            self.scheduler_mode = True
            # if the workflows doesn't have an interval, set the default interval
            for workflow in workflows:
                workflow.workflow_interval = workflow.workflow_interval
            # This will halt until KeyboardInterrupt
            self.scheduler.run_workflows(workflows)
            self.logger.info("Workflow(s) scheduled")
        else:
            # running workflows in the regular mode
            workflows_errors = self._run_workflows_from_cli(workflows)

        return workflows_errors

    def _check_premium_providers(self, workflow: Workflow):
        """
        Check if the workflow uses premium providers in multi tenant mode.

        Args:
            workflow (Workflow): The workflow to check.

        Raises:
            Exception: If the workflow uses premium providers in multi tenant mode.
        """
        if (
            os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
            == AuthenticationType.MULTI_TENANT.value
        ):
            for provider in workflow.workflow_providers_type:
                if provider in self.PREMIUM_PROVIDERS:
                    raise Exception(
                        f"Provider {provider} is a premium provider. You can self-host or contact us to get access to it."
                    )

    def _run_workflow(self, workflow: Workflow, workflow_execution_id: str):
        self.logger.info(f"Running workflow {workflow.workflow_id}")
        errors = []
        try:
            self._check_premium_providers(workflow)
            errors = workflow.run(workflow_execution_id)
        except Exception as e:
            self.logger.error(
                f"Error running workflow {workflow.workflow_id}",
                extra={"exception": e, "workflow_execution_id": workflow_execution_id},
            )
            if workflow.on_failure:
                self.logger.info(
                    f"Running on_failure action for workflow {workflow.workflow_id}"
                )
                # Adding the exception message to the provider context so it'll be available for the action
                message = (
                    f"Workflow {workflow.workflow_id} failed with exception: {str(e)}å"
                )
                workflow.on_failure.provider_parameters = {"message": message}
                workflow.on_failure.run()
            raise
        finally:
            # todo - state should be saved in db
            workflow.context_manager.dump()

        self._save_workflow_results(workflow, workflow_execution_id)
        if any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
        else:
            self.logger.info(f"Workflow {workflow.workflow_id} ran successfully")

        return errors

    def _save_workflow_results(self, workflow: Workflow, workflow_execution_id: str):
        """
        Save the results of the workflow to the DB.

        Args:
            workflow (Workflow): The workflow to save.
            workflow_execution_id (str): The workflow execution ID.
        """
        self.logger.info(f"Saving workflow {workflow.workflow_id} results")
        workflow_results = {
            action.name: action.provider.results for action in workflow.workflow_actions
        }
        try:
            save_workflow_results(
                tenant_id=workflow.context_manager.tenant_id,
                workflow_execution_id=workflow_execution_id,
                workflow_results=workflow_results,
            )
        except Exception as e:
            self.logger.error(
                f"Error saving workflow {workflow.workflow_id} results",
                extra={"exception": e},
            )
            raise
        self.logger.info(f"Workflow {workflow.workflow_id} results saved")

    def _run_workflows_from_cli(self, workflows: typing.List[Workflow]):
        workflows_errors = []
        for workflow in workflows:
            try:
                random_workflow_id = str(uuid.uuid4())
                errors = self._run_workflow(
                    workflow, workflow_execution_id=random_workflow_id
                )
                workflows_errors.append(errors)
            except Exception as e:
                self.logger.error(
                    f"Error running workflow {workflow.workflow_id}",
                    extra={"exception": e},
                )
                raise

        return workflows_errors
