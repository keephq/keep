import logging
import os
import re
import typing
import uuid
from threading import Lock

from keep.api.core.config import config
from keep.api.core.db import (
    get_enrichment,
    get_previous_alert_by_fingerprint,
    save_workflow_results,
)
from keep.api.core.metrics import workflow_execution_duration
from keep.api.models.alert import AlertDto, AlertSeverity, IncidentDto
from keep.identitymanager.identitymanagerfactory import IdentityManagerTypes
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowscheduler import WorkflowScheduler, timing_histogram
from keep.workflowmanager.workflowstore import WorkflowStore


class WorkflowManager:
    # List of providers that are not allowed to be used in workflows in multi tenant mode.
    PREMIUM_PROVIDERS = ["bash", "python"]

    _instance = None
    _instance_lock = Lock()

    @classmethod
    def get_instance(cls) -> "WorkflowManager":
        with cls._instance_lock:
            if not cls._instance:
                cls._instance = WorkflowManager()
            return cls._instance

    def __init__(self):
        # thread safety
        if hasattr(WorkflowManager, "_initialized"):
            return
        self.logger = logging.getLogger(__name__)
        self.debug = config("WORKFLOW_MANAGER_DEBUG", default=False, cast=bool)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
        self.scheduler = WorkflowScheduler(self)
        self.workflow_store = WorkflowStore()
        self.started = False
        # Mark as initialized
        WorkflowManager._initialized = True

    async def start(self):
        """Runs the workflow manager in server mode"""
        if self.started:
            self.logger.info("Workflow manager already started")
            return
        await self.scheduler.start()
        self.started = True

    def stop(self):
        """Stops the workflow manager"""
        if not self.started:
            return
        self.scheduler.stop()
        self.started = False
        # Clear the scheduler reference
        self.scheduler = None

    def _apply_filter(self, filter_val, value):
        # if it's a regex, apply it
        if isinstance(filter_val, str) and filter_val.startswith('r"'):
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
            # For cases like `dismissed`
            if isinstance(filter_val, bool) and isinstance(value, str):
                return value == str(filter_val)
            return value == filter_val

    def _get_workflow_from_store(self, tenant_id, workflow_model):
        try:
            # get the actual workflow that can be triggered
            self.logger.info("Getting workflow from store")
            workflow = self.workflow_store.get_workflow(tenant_id, workflow_model.id)
            self.logger.info("Got workflow from store")
            return workflow
        except ProviderConfigurationException:
            self.logger.exception(
                "Workflow have a provider that is not configured",
                extra={
                    "workflow_id": workflow_model.id,
                    "tenant_id": tenant_id,
                },
            )
        except Exception:
            self.logger.exception(
                "Error getting workflow",
                extra={
                    "workflow_id": workflow_model.id,
                    "tenant_id": tenant_id,
                },
            )

    def insert_incident(self, tenant_id: str, incident: IncidentDto, trigger: str):
        all_workflow_models = self.workflow_store.get_all_workflows(tenant_id)
        self.logger.info(
            "Got all workflows",
            extra={
                "num_of_workflows": len(all_workflow_models),
            },
        )
        for workflow_model in all_workflow_models:

            if workflow_model.is_disabled:
                self.logger.debug(
                    f"Skipping the workflow: id={workflow_model.id}, name={workflow_model.name}, "
                    f"tenant_id={workflow_model.tenant_id} - Workflow is disabled."
                )
                continue
            workflow = self._get_workflow_from_store(tenant_id, workflow_model)
            if workflow is None:
                continue

            # Using list comprehension instead of pandas flatten() for better performance
            # and to avoid pandas dependency
            # @tb: I removed pandas so if we'll have performance issues we can revert to pandas
            incident_triggers = [
                event
                for trigger in workflow.workflow_triggers
                if trigger["type"] == "incident"
                for event in trigger.get("events", [])
            ]

            if trigger not in incident_triggers:
                self.logger.debug(
                    "workflow does not contain trigger %s, skipping", trigger
                )
                continue

            self.logger.info("Adding workflow to run")
            with self.scheduler.lock:
                self.scheduler.workflows_to_run.append(
                    {
                        "workflow": workflow,
                        "workflow_id": workflow_model.id,
                        "tenant_id": tenant_id,
                        "triggered_by": "incident:{}".format(trigger),
                        "event": incident,
                    }
                )
            self.logger.info("Workflow added to run")

    def insert_events(self, tenant_id, events: typing.List[AlertDto | IncidentDto]):
        for event in events:
            self.logger.info("Getting all workflows")
            all_workflow_models = self.workflow_store.get_all_workflows(tenant_id)
            self.logger.info(
                "Got all workflows",
                extra={
                    "num_of_workflows": len(all_workflow_models),
                },
            )
            for workflow_model in all_workflow_models:

                if workflow_model.is_disabled:
                    self.logger.debug(
                        f"Skipping the workflow: id={workflow_model.id}, name={workflow_model.name}, "
                        f"tenant_id={workflow_model.tenant_id} - Workflow is disabled."
                    )
                    continue
                workflow = self._get_workflow_from_store(tenant_id, workflow_model)
                if workflow is None:
                    continue

                for trigger in workflow.workflow_triggers:
                    # TODO: handle it better
                    if not trigger.get("type") == "alert":
                        self.logger.debug("trigger type is not alert, skipping")
                        continue
                    should_run = True
                    # apply filters
                    for filter in trigger.get("filters", []):
                        # TODO: more sophisticated filtering/attributes/nested, etc
                        self.logger.debug(f"Running filter {filter}")
                        filter_key = filter.get("key")
                        filter_val = filter.get("value")
                        event_val = self._get_event_value(event, filter_key)
                        self.logger.debug(
                            "Filtering",
                            extra={
                                "filter_key": filter_key,
                                "filter_val": filter_val,
                                "event": event,
                            },
                        )
                        if event_val is None:
                            self.logger.warning(
                                "Failed to run filter, skipping the event. Probably misconfigured workflow.",
                                extra={
                                    "tenant_id": tenant_id,
                                    "filter_key": filter_key,
                                    "filter_val": filter_val,
                                    "workflow_id": workflow_model.id,
                                },
                            )
                            should_run = False
                            continue
                        # if its list, check if the filter is in the list
                        if isinstance(event_val, list):
                            for val in event_val:
                                # if one filter applies, it should run
                                if self._apply_filter(filter_val, val):
                                    self.logger.debug(
                                        "Filter matched, running",
                                        extra={
                                            "filter_key": filter_key,
                                            "filter_val": filter_val,
                                            "event": event,
                                        },
                                    )
                                    should_run = True
                                    break
                                self.logger.debug(
                                    "Filter didn't match, skipping",
                                    extra={
                                        "filter_key": filter_key,
                                        "filter_val": filter_val,
                                        "event": event,
                                    },
                                )
                                should_run = False
                        # elif the filter is string/int/float, compare them:
                        elif type(event_val) in [int, str, float, bool]:
                            if not self._apply_filter(filter_val, event_val):
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

                    if not should_run:
                        self.logger.debug("Skipping the workflow")
                        continue
                    # enrich the alert with more data
                    self.logger.info("Found a workflow to run")
                    event.trigger = "alert"
                    # prepare the alert with the enrichment
                    self.logger.info("Enriching alert")
                    alert_enrichment = get_enrichment(tenant_id, event.fingerprint)
                    if alert_enrichment:
                        for k, v in alert_enrichment.enrichments.items():
                            setattr(event, k, v)
                    self.logger.info("Alert enriched")
                    # apply only_on_change (https://github.com/keephq/keep/issues/801)
                    fields_that_needs_to_be_change = trigger.get("only_on_change", [])
                    severity_changed = trigger.get("severity_changed", False)
                    # if there are fields that needs to be changed, get the previous alert
                    if fields_that_needs_to_be_change or severity_changed:
                        previous_alert = get_previous_alert_by_fingerprint(
                            tenant_id, event.fingerprint
                        )
                        if severity_changed:
                            fields_that_needs_to_be_change.append("severity")
                        # now compare:
                        #   (no previous alert means that the workflow should run)
                        if previous_alert:
                            for field in fields_that_needs_to_be_change:
                                # the field hasn't change
                                if getattr(event, field) == previous_alert.event.get(
                                    field
                                ):
                                    self.logger.info(
                                        "Skipping the workflow because the field hasn't change",
                                        extra={
                                            "field": field,
                                            "event": event,
                                            "previous_alert": previous_alert,
                                        },
                                    )
                                    should_run = False
                                    break
                            if should_run and severity_changed:
                                setattr(event, "severity_changed", True)
                                setattr(
                                    event,
                                    "previous_severity",
                                    previous_alert.event.get("severity"),
                                )
                                previous_severity = AlertSeverity(
                                    previous_alert.event.get("severity")
                                )
                                current_severity = AlertSeverity(event.severity)
                                if previous_severity < current_severity:
                                    setattr(event, "severity_change", "increased")
                                else:
                                    setattr(event, "severity_change", "decreased")

                    if not should_run:
                        continue
                    # Lastly, if the workflow should run, add it to the scheduler
                    self.logger.info("Adding workflow to run")
                    with self.scheduler.lock:
                        self.scheduler.workflows_to_run.append(
                            {
                                "workflow": workflow,
                                "workflow_id": workflow_model.id,
                                "tenant_id": tenant_id,
                                "triggered_by": "alert",
                                "event": event,
                            }
                        )
                    self.logger.info("Workflow added to run")

    def _get_event_value(self, event, filter_key):
        # if the filter key is a nested key, get the value
        if "." in filter_key:
            filter_key_split = filter_key.split(".")
            # event is alert dto so we need getattr
            event_val = getattr(event, filter_key_split[0], None)
            if not event_val:
                return None
            # iterate the other keys
            for key in filter_key_split[1:]:
                event_val = event_val.get(key, None)
                # if the key doesn't exist, return None because we didn't find the value
                if not event_val:
                    return None
            return event_val
        else:
            return getattr(event, filter_key, None)

    def _check_premium_providers(self, workflow: Workflow):
        """
        Check if the workflow uses premium providers in multi tenant mode.

        Args:
            workflow (Workflow): The workflow to check.

        Raises:
            Exception: If the workflow uses premium providers in multi tenant mode.
        """
        if os.environ.get("AUTH_TYPE", IdentityManagerTypes.NOAUTH.value) in (
            IdentityManagerTypes.AUTH0.value,
            "MULTI_TENANT",
        ):  # backward compatibility
            for provider in workflow.workflow_providers_type:
                if provider in self.PREMIUM_PROVIDERS:
                    raise Exception(
                        f"Provider {provider} is a premium provider. You can self-host or contact us to get access to it."
                    )

    def _run_workflow_on_failure(
        self, workflow: Workflow, workflow_execution_id: str, error_message: str
    ):
        """
        Runs the workflow on_failure action.

        Args:
            workflow (Workflow): The workflow that fails
            workflow_execution_id (str): Workflow execution id
            error_message (str): The error message(s)
        """
        if workflow.on_failure:
            self.logger.info(
                f"Running on_failure action for workflow {workflow.workflow_id}",
                extra={
                    "workflow_execution_id": workflow_execution_id,
                    "workflow_id": workflow.workflow_id,
                    "tenant_id": workflow.context_manager.tenant_id,
                },
            )
            # Adding the exception message to the provider context, so it'll be available for the action
            message = (
                f"Workflow {workflow.workflow_id} failed with errors: {error_message}"
            )
            workflow.on_failure.provider_parameters = {"message": message}
            workflow.on_failure.run()
            self.logger.info(
                "Ran on_failure action for workflow",
                extra={
                    "workflow_execution_id": workflow_execution_id,
                    "workflow_id": workflow.workflow_id,
                    "tenant_id": workflow.context_manager.tenant_id,
                },
            )
        else:
            self.logger.debug(
                "No on_failure configured for workflow",
                extra={
                    "workflow_execution_id": workflow_execution_id,
                    "workflow_id": workflow.workflow_id,
                    "tenant_id": workflow.context_manager.tenant_id,
                },
            )

    @timing_histogram(workflow_execution_duration)
    def _run_workflow(
        self, workflow: Workflow, workflow_execution_id: str, test_run=False
    ):
        self.logger.debug(f"Running workflow {workflow.workflow_id}")
        errors = []
        results = {}
        try:
            self._check_premium_providers(workflow)
            errors = workflow.run(workflow_execution_id)
            if errors:
                self._run_workflow_on_failure(
                    workflow, workflow_execution_id, ", ".join(errors)
                )
        except Exception as e:
            self.logger.error(
                f"Error running workflow {workflow.workflow_id}",
                extra={"exception": e, "workflow_execution_id": workflow_execution_id},
            )
            self._run_workflow_on_failure(workflow, workflow_execution_id, str(e))
            raise
        finally:
            if not test_run:
                workflow.context_manager.dump()

        if any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
        else:
            self.logger.info(f"Workflow {workflow.workflow_id} ran successfully")

        if test_run:
            results = self._get_workflow_results(workflow)
        else:
            self._save_workflow_results(workflow, workflow_execution_id)

        return [errors, results]

    @staticmethod
    def _get_workflow_results(workflow: Workflow):
        """
        Get the results of the workflow from the DB.

        Args:
            workflow (Workflow): The workflow to get the results for.

        Returns:
            dict: The results of the workflow.
        """

        workflow_results = {
            action.name: action.provider.results for action in workflow.workflow_actions
        }
        if workflow.workflow_steps:
            workflow_results.update(
                {step.name: step.provider.results for step in workflow.workflow_steps}
            )
        return workflow_results

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
        if workflow.workflow_steps:
            workflow_results.update(
                {step.name: step.provider.results for step in workflow.workflow_steps}
            )
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
                errors, _ = self._run_workflow(
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
