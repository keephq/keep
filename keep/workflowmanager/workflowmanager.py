import logging
import os
import re
import threading
import typing
import uuid

import celpy

from keep.api.core.config import config
from keep.api.core.db import (
    get_enrichment,
    get_previous_alert_by_fingerprint,
    save_workflow_results,
)
from keep.api.core.metrics import workflow_execution_duration
from keep.api.models.alert import AlertDto, AlertSeverity
from keep.api.models.incident import IncidentDto
from keep.identitymanager.identitymanagerfactory import IdentityManagerTypes
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowscheduler import WorkflowScheduler, timing_histogram
from keep.workflowmanager.workflowstore import WorkflowStore
from keep.api.utils.cel_utils import preprocess_cel_expression


class WorkflowManager:
    # List of providers that are not allowed to be used in workflows in multi tenant mode.
    PREMIUM_PROVIDERS = ["bash", "python", "llamacpp", "ollama"]

    @staticmethod
    def get_instance() -> "WorkflowManager":
        if not hasattr(WorkflowManager, "_instance"):
            WorkflowManager._instance = WorkflowManager()
        return WorkflowManager._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.debug = config("WORKFLOW_MANAGER_DEBUG", default=False, cast=bool)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)

        self.scheduler = WorkflowScheduler(self)
        self.workflow_store = WorkflowStore()
        self.started = False
        self.cel_environment = celpy.Environment()
        # this is to enqueue the workflows in the REDIS queue
        # SHAHAR: todo - finish the REDIS implementation
        # self.loop = None
        # self.redis = config("REDIS", default="false").lower() == "true"

    async def start(self):
        """Runs the workflow manager in server mode"""
        if self.started:
            self.logger.info("Workflow manager already started")
            return

        if not self.scheduler:
            self.logger.error("Scheduler is not initialized, initializing it")
            self.scheduler = WorkflowScheduler(self)

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
            self.logger.warning(
                "Workflow have a provider that is not configured",
                extra={
                    "workflow_id": workflow_model.id,
                    "tenant_id": tenant_id,
                },
            )
        except Exception as ex:
            self.logger.warning(
                "Error getting workflow",
                exc_info=ex,
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

            incident_enrichment = get_enrichment(tenant_id, str(incident.id))
            if incident_enrichment:
                for k, v in incident_enrichment.enrichments.items():
                    setattr(incident, k, v)

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

    # @tb: should I move it to cel_utils.py?
    # logging is easier here and I don't see other places who might use this >.<
    def _convert_filters_to_cel(self, filters: list[dict[str, str]]):
        # Convert filters ({"key": "key", "value": "value"}) and friends to CEL
        self.logger.info(
            "Converting filters to CEL",
            extra={"original_filters": filters},
        )
        try:
            cel_filters = []
            for filter in filters:
                key = filter.get("key")
                value = filter.get("value")
                exclude = filter.get("exclude", False)

                # malformed filter?
                if not key or not value:
                    self.logger.warning(
                        "Filter is missing key or value",
                        extra={"filter": filter},
                    )
                    continue

                if value.startswith('r"'):
                    # Try to parse regex in to CEL
                    cel_regex = []
                    value = value[2:-1]

                    # for example: value: r"error\\.[a-z]+\\..*" is to hard to convert to CEL
                    # so we'll just hit the last else and raise an exception, that it's deprecated
                    if "]^" in value or "]+" in value:
                        raise Exception(
                            f"Unsupported regex: {value}, move to new CEL filters"
                        )
                    elif "|" in value:
                        value_split = value.split("|")
                        for value_ in value_split:
                            value_ = value_.lstrip("(").rstrip(")").strip()
                            if key == "source":
                                if exclude:
                                    cel_regex.append(f'!{key}.contains("{value_}")')
                                else:
                                    cel_regex.append(f'{key}.contains("{value_}")')
                            else:
                                if exclude:
                                    cel_regex.append(f'{key} != "{value_}"')
                                else:
                                    cel_regex.append(f'{key} == "{value_}"')
                    elif value == ".*":
                        cel_regex.append(f"has({key})")
                    elif value == "^$":
                        # empty string
                        if exclude:
                            cel_regex.append(f'{key} != ""')
                        else:
                            cel_regex.append(f'{key} == ""')
                    elif value.startswith(".*") and value.endswith(".*"):
                        # for example: r".*prometheus.*"
                        if exclude:
                            cel_regex.append(f'!{key}.contains("{value[2:-2]}")')
                        else:
                            cel_regex.append(f'{key}.contains("{value[2:-2]}")')
                    elif value.endswith(".*"):
                        # for example: r"2025-01-30T09:.*"
                        if exclude:
                            cel_regex.append(f'!{key}.contains("{value[:-2]}")')
                        else:
                            cel_regex.append(f'{key}.contains("{value[:-2]}")')
                    else:
                        raise Exception(
                            f"Unsupported regex: {value}, move to new CEL filters"
                        )
                    # if we're talking about excluded, we need to do AND between the regexes
                    # for example:
                    #   filters: [{"key": "source", "value": 'r"prometheus|grafana"', "exclude": true}]
                    #   cel: !source.contains("prometheus") && !source.contains("grafana")
                    # otherwise, we do OR between the regexes
                    # for example:
                    #   filters: [{"key": "source", "value": 'r"prometheus|grafana"'}]
                    #   cel: source.contains("prometheus") || source.contains("grafana")
                    if exclude:
                        cel_filters.append(f"({' && '.join(cel_regex)})")
                    else:
                        cel_filters.append(f"({' || '.join(cel_regex)})")
                else:
                    if key == "source":
                        # handle source, which is a list of sources
                        if exclude:
                            cel_filters.append(f'!{key}.contains("{value}")')
                        else:
                            cel_filters.append(f'{key}.contains("{value}")')
                    else:
                        if exclude:
                            cel_filters.append(f'{key} != "{value}"')
                        else:
                            cel_filters.append(f'{key} == "{value}"')

            self.logger.info(
                "Converted filters to CEL",
                extra={"cel_filters": cel_filters, "original_filters": filters},
            )

            return " && ".join(cel_filters)
        except Exception as e:
            self.logger.exception(
                "Error converting filters to CEL", extra={"exception": e}
            )
            raise

    def insert_events(self, tenant_id, events: typing.List[AlertDto | IncidentDto]):
        for event in events:
            self.logger.info("Getting all workflows", extra={"tenant_id": tenant_id})
            all_workflow_models = self.workflow_store.get_all_workflows(
                tenant_id, exclude_disabled=True
            )
            self.logger.info(
                "Got all workflows",
                extra={
                    "num_of_workflows": len(all_workflow_models),
                    "tenant_id": tenant_id,
                },
            )
            for workflow_model in all_workflow_models:
                workflow = self._get_workflow_from_store(tenant_id, workflow_model)

                if workflow is None:
                    # Exception is thrown in _get_workflow_from_store, we don't need to log it here, just continue.
                    continue

                for trigger in workflow.workflow_triggers:
                    # If the trigger is not an alert, it's not relevant for this event.
                    if not trigger.get("type") == "alert":
                        self.logger.debug(
                            "Trigger type is not alert, skipping",
                            extra={
                                "trigger": trigger,
                                "workflow_id": workflow_model.id,
                                "tenant_id": tenant_id,
                            },
                        )
                        continue

                    if "filters" not in trigger and "cel" not in trigger:
                        self.logger.warning(
                            "Trigger is missing filters or cel",
                            extra={
                                "trigger": trigger,
                                "workflow_id": workflow_model.id,
                                "tenant_id": tenant_id,
                            },
                        )
                        should_run = True
                    else:

                        # By default, the workflow should not run. Only if the CEL evaluates to true, the workflow will run.
                        should_run = False

                        # backward compatibility for filter. should be removed in the future
                        # if triggers and cel are set, we override the cel with filters.
                        if "filters" in trigger:
                            try:
                                # this is old format, so let's convert it to CEL
                                trigger["cel"] = self._convert_filters_to_cel(
                                    trigger["filters"]
                                )
                            except Exception:
                                self.logger.exception(
                                    "Failed to convert filters to CEL, workflow will not run",
                                    extra={
                                        "trigger": trigger,
                                        "workflow_id": workflow_model.id,
                                        "tenant_id": tenant_id,
                                    },
                                )
                                continue

                        cel = trigger.get("cel", "")
                        if not cel:
                            self.logger.warning(
                                "Trigger is missing cel",
                                extra={
                                    "trigger": trigger,
                                    "workflow_id": workflow_model.id,
                                    "tenant_id": tenant_id,
                                },
                            )
                            continue

                        # source is a special case which can be used as string comparison although it is a list
                        if "source" in cel:
                            try:
                                self.logger.info(
                                    "Checking if source needs to be replaced",
                                    extra={
                                        "cel": cel,
                                        "trigger": trigger,
                                        "workflow_id": workflow_model.id,
                                        "tenant_id": tenant_id,
                                    },
                                )
                                pattern = r'source\s*==\s*[\'"]([^\'"]+)[\'"]'
                                replacement = r'source.contains("\1")'
                                cel = re.sub(pattern, replacement, cel)
                            except Exception:
                                self.logger.exception(
                                    "Error replacing source in CEL",
                                    extra={
                                        "cel": cel,
                                        "trigger": trigger,
                                        "workflow_id": workflow_model.id,
                                        "tenant_id": tenant_id,
                                    },
                                )
                                continue

                        # Preprocess the CEL expression to handle severity comparisons properly
                        try:
                            cel = preprocess_cel_expression(cel)
                            self.logger.debug(
                                "Preprocessed CEL expression",
                                extra={
                                    "original_cel": trigger.get("cel", ""),
                                    "preprocessed_cel": cel,
                                    "workflow_id": workflow_model.id,
                                    "tenant_id": tenant_id,
                                },
                            )
                        except Exception:
                            self.logger.exception(
                                "Error preprocessing CEL expression",
                                extra={
                                    "cel": cel,
                                    "trigger": trigger,
                                    "workflow_id": workflow_model.id,
                                    "tenant_id": tenant_id,
                                },
                            )
                            continue

                        compiled_ast = self.cel_environment.compile(cel)
                        program = self.cel_environment.program(compiled_ast)
                        
                        # Convert event to dict and normalize severity for CEL evaluation
                        event_payload = event.dict()
                        # Convert severity string to numeric order for proper comparison with preprocessed CEL
                        if isinstance(event_payload.get("severity"), str):
                            try:
                                event_payload["severity"] = AlertSeverity(event_payload["severity"].lower()).order
                            except (ValueError, AttributeError):
                                # If severity conversion fails, keep original value
                                pass
                        
                        activation = celpy.json_to_cel(event_payload)
                        try:
                            should_run = program.evaluate(activation)
                        except celpy.evaluation.CELEvalError as e:
                            self.logger.exception(
                                "Error evaluating CEL for event in insert_events",
                                extra={
                                    "exception": e,
                                    "event": event,
                                    "trigger": trigger,
                                    "workflow_id": workflow_model.id,
                                    "tenant_id": tenant_id,
                                    "cel": trigger["cel"],
                                    "deprecated_filters": trigger.get("filters"),
                                },
                            )
                            continue

                    if bool(should_run) is False:
                        self.logger.debug(
                            "Workflow should not run, skipping",
                            extra={
                                "triggers": workflow.workflow_triggers,
                                "workflow_id": workflow_model.id,
                                "tenant_id": tenant_id,
                                "cel": trigger["cel"],
                                "deprecated_filters": trigger.get("filters"),
                            },
                        )
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

                    # SHAHAR: TODO - finish redis implementation
                    # if REDIS is enabled, add the workflow to the queue

                    """
                    if os.environ.get("REDIS", "false").lower() == "true":
                        try:
                            self.logger.info("Adding workflow to REDIS")
                            from arq import ArqRedis
                            from keep.api.arq_pool import get_pool
                            from keep.api.consts import KEEP_ARQ_QUEUE_WORKFLOWS

                            # We need to run this asynchronously
                            async def enqueue_workflow():
                                redis: ArqRedis = await get_pool()
                                job = await redis.enqueue_job(
                                    "run_workflow_in_worker",  # You'll need to create this function
                                    tenant_id,
                                    str(workflow_model.id),  # Convert UUID to string if needed
                                    "alert",  # triggered_by
                                    event,  # Pass the event
                                    _queue_name=KEEP_ARQ_QUEUE_WORKFLOWS,
                                )
                                self.logger.info(
                                    "Enqueued workflow job",
                                    extra={
                                        "job_id": job.job_id,
                                        "workflow_id": workflow_model.id,
                                        "tenant_id": tenant_id,
                                        "queue": KEEP_ARQ_QUEUE_WORKFLOWS,
                                    },
                                )

                            # Execute the async function
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            job_id = loop.run_until_complete(enqueue_workflow())
                            self.logger.info("Job enqueued", extra={"job_id": job_id})
                        except Exception as e:
                            self.logger.error(
                                "Failed to enqueue workflow job",
                                extra={
                                    "exception": str(e),
                                    "workflow_id": workflow_model.id,
                                    "tenant_id": tenant_id,
                                },
                            )
                    """
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
            self.logger.info("All workflows added to run")

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
            # TODO: maybe to set the message in step.vars instead of provider_parameters so user can format it
            workflow.on_failure.provider_parameters = {
                **workflow.on_failure.provider_parameters,
                "message": message,
            }
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
    def _run_workflow(self, workflow: Workflow, workflow_execution_id: str):
        self.logger.debug(f"Running workflow {workflow.workflow_id}")
        threading.current_thread().workflow_debug = workflow.workflow_debug
        threading.current_thread().workflow_id = workflow.workflow_id
        threading.current_thread().workflow_execution_id = workflow_execution_id
        threading.current_thread().tenant_id = workflow.context_manager.tenant_id
        errors = []
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

        if errors is not None and any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
        else:
            self.logger.info(f"Workflow {workflow.workflow_id} ran successfully")

        self._save_workflow_results(workflow, workflow_execution_id)

        return [errors, None]

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
