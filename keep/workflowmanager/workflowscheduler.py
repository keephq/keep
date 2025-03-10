import enum
import hashlib
import logging
import queue
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from threading import Lock

from sqlalchemy.exc import IntegrityError

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.core.db import create_workflow_execution
from keep.api.core.db import finish_workflow_execution as finish_workflow_execution_db
from keep.api.core.db import (
    get_enrichment,
    get_previous_execution_id,
    get_timeouted_workflow_exections,
)
from keep.api.core.db import get_workflow as get_workflow_db
from keep.api.core.db import get_workflows_that_should_run
from keep.api.core.metrics import (
    workflow_execution_errors_total,
    workflow_execution_status,
    workflow_executions_total,
    workflow_queue_size,
    workflows_running,
)
from keep.api.models.alert import AlertDto
from keep.api.models.incident import IncidentDto
from keep.api.utils.email_utils import KEEP_EMAILS_ENABLED, EmailTemplates, send_email
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow, WorkflowStrategy
from keep.workflowmanager.workflowstore import WorkflowStore

READ_ONLY_MODE = config("KEEP_READ_ONLY", default="false") == "true"
MAX_WORKERS = config("WORKFLOWS_MAX_WORKERS", default="20")


class WorkflowStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    PROVIDERS_NOT_CONFIGURED = "providers_not_configured"


def timing_histogram(histogram):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                # Try to get tenant_id and workflow_id from self
                try:
                    tenant_id = args[1].context_manager.tenant_id
                except Exception:
                    tenant_id = "unknown"
                try:
                    workflow_id = args[1].workflow_id
                except Exception:
                    workflow_id = "unknown"
                histogram.labels(tenant_id=tenant_id, workflow_id=workflow_id).observe(
                    duration
                )

        return wrapper

    return decorator


class WorkflowScheduler:
    MAX_SIZE_SIGNED_INT = 2147483647
    MAX_WORKERS = config("KEEP_MAX_WORKFLOW_WORKERS", default="20", cast=int)

    def __init__(self, workflow_manager):
        self.logger = logging.getLogger(__name__)
        self.workflow_manager = workflow_manager
        self.workflow_store = WorkflowStore()
        # all workflows that needs to be run due to alert event
        self.workflows_to_run = []
        self._stop = False
        self.lock = Lock()
        self.interval_enabled = (
            config("WORKFLOWS_INTERVAL_ENABLED", default="true") == "true"
        )
        self.executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix="WorkflowScheduler",
        )
        self.scheduler_future = None
        self.futures = set()
        # Initialize metrics for queue size
        self._update_queue_metrics()

    def _update_queue_metrics(self):
        """Update queue size metrics"""
        with self.lock:
            for workflow in self.workflows_to_run:
                tenant_id = workflow.get("tenant_id", "unknown")
                workflow_queue_size.labels(tenant_id=tenant_id).set(
                    len(self.workflows_to_run)
                )

    async def start(self):
        self.logger.info("Starting workflows scheduler")
        # Shahar: fix for a bug in unit tests
        self._stop = False
        self.scheduler_future = self.executor.submit(self._start)
        self.logger.info("Workflows scheduler started")

    def _handle_interval_workflows(self):
        workflows = []

        if not self.interval_enabled:
            self.logger.debug("Interval workflows are disabled")
            return

        try:
            # get all workflows that should run due to interval
            workflows = get_workflows_that_should_run()
        except Exception:
            self.logger.exception("Error getting workflows that should run")
            pass
        for workflow in workflows:
            workflow_execution_id = workflow.get("workflow_execution_id")
            tenant_id = workflow.get("tenant_id")
            workflow_id = workflow.get("workflow_id")

            try:
                workflow_obj = self.workflow_store.get_workflow(tenant_id, workflow_id)
            except ProviderConfigurationException:
                self.logger.exception(
                    "Provider configuration is invalid",
                    extra={
                        "workflow_id": workflow_id,
                        "workflow_execution_id": workflow_execution_id,
                        "tenant_id": tenant_id,
                    },
                )
                self._finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    workflow_execution_id=workflow_execution_id,
                    status=WorkflowStatus.PROVIDERS_NOT_CONFIGURED,
                    error=f"Providers are not configured for workflow {workflow_id}",
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"Error getting workflow: {e}",
                    extra={
                        "workflow_id": workflow_id,
                        "workflow_execution_id": workflow_execution_id,
                        "tenant_id": tenant_id,
                    },
                )
                self._finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    workflow_execution_id=workflow_execution_id,
                    status=WorkflowStatus.ERROR,
                    error=f"Error getting workflow: {e}",
                )
                continue

            future = self.executor.submit(
                self._run_workflow,
                tenant_id,
                workflow_id,
                workflow_obj,
                workflow_execution_id,
            )
            self.futures.add(future)
            future.add_done_callback(lambda f: self.futures.remove(f))

    def _run_workflow(
        self,
        tenant_id,
        workflow_id,
        workflow: Workflow,
        workflow_execution_id: str,
        event_context=None,
    ):
        if READ_ONLY_MODE:
            self.logger.debug("Sleeping for 3 seconds in favor of read only mode")
            time.sleep(3)

        self.logger.info(f"Running workflow {workflow.workflow_id}...")

        try:
            # Increment running workflows counter
            workflows_running.labels(tenant_id=tenant_id).inc()

            # Track execution
            # Shahar: currently incident doesn't have trigger so we will workaround it
            if isinstance(event_context, AlertDto):
                workflow_executions_total.labels(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    trigger_type=event_context.trigger if event_context else "interval",
                ).inc()
            else:
                # TODO: add trigger to incident
                workflow_executions_total.labels(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    trigger_type="incident",
                ).inc()

            # Run the workflow
            if isinstance(event_context, AlertDto):
                workflow.context_manager.set_event_context(event_context)
            else:
                workflow.context_manager.set_incident_context(event_context)

            errors, _ = self.workflow_manager._run_workflow(
                workflow, workflow_execution_id
            )
        except Exception as e:
            # Track error metrics
            workflow_execution_errors_total.labels(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                error_type=type(e).__name__,
            ).inc()

            workflow_execution_status.labels(
                tenant_id=tenant_id, workflow_id=workflow_id, status="error"
            ).inc()

            self.logger.exception(
                f"Failed to run workflow {workflow.workflow_id}...",
                extra={
                    "workflow_id": workflow_id,
                    "workflow_execution_id": workflow_execution_id,
                    "tenant_id": tenant_id,
                },
            )
            self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.ERROR,
                error=str(e),
            )
            return
        finally:
            # Decrement running workflows counter
            workflows_running.labels(tenant_id=tenant_id).dec()
            self._update_queue_metrics()

        if errors is not None and any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
            self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.ERROR,
                error="\n".join(str(e) for e in errors),
            )
        else:
            self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.SUCCESS,
                error=None,
            )

        self.logger.info(f"Workflow {workflow.workflow_id} ran")

    def handle_workflow_test(self, workflow, tenant_id, triggered_by_user):
        workflow_execution_id = self._get_unique_execution_number()

        self.logger.info(
            "Adding workflow to run",
            extra={
                "workflow_id": workflow.workflow_id,
                "workflow_execution_id": workflow_execution_id,
                "tenant_id": tenant_id,
                "triggered_by": "manual",
                "triggered_by_user": triggered_by_user,
            },
        )

        result_queue = queue.Queue()

        def run_workflow_wrapper(
            run_workflow, workflow, workflow_execution_id, test_run, result_queue
        ):
            try:
                errors, results = run_workflow(
                    workflow, workflow_execution_id, test_run
                )
                result_queue.put((errors, results))
            except Exception as e:
                print(f"Exception in workflow: {e}")
                # errors are expected to be a list of strings, so we wrap it
                result_queue.put(([str(e)], None))

        future = self.executor.submit(
            run_workflow_wrapper,
            self.workflow_manager._run_workflow,
            workflow,
            workflow_execution_id,
            True,
            result_queue,
        )
        future.result()  # Wait for completion
        errors, results = result_queue.get()

        status = "success"
        error = None
        if errors is not None and any(errors):
            error = "\n".join(str(e) for e in errors)
            status = "error"

        self.logger.info(
            "Workflow test complete",
            extra={
                "workflow_id": workflow.workflow_id,
                "workflow_execution_id": workflow_execution_id,
                "tenant_id": tenant_id,
                "status": status,
                "error": error,
                "results": results,
            },
        )

        return {
            "workflow_execution_id": workflow_execution_id,
            "status": status,
            "error": error,
            "results": results,
        }

    def handle_manual_event_workflow(
        self, workflow_id, tenant_id, triggered_by_user, event: [AlertDto | IncidentDto]
    ):
        self.logger.info(f"Running manual event workflow {workflow_id}...")
        try:
            unique_execution_number = self._get_unique_execution_number()
            self.logger.info(f"Unique execution number: {unique_execution_number}")

            if isinstance(event, IncidentDto):
                event_id = str(event.id)
                event_type = "incident"
                fingerprint = "incident:{}".format(event_id)
            else:
                event_id = event.event_id
                event_type = "alert"
                fingerprint = event.fingerprint

            workflow_execution_id = create_workflow_execution(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                triggered_by=f"manually by {triggered_by_user}",
                execution_number=unique_execution_number,
                fingerprint=fingerprint,
                event_id=event_id,
                event_type=event_type,
            )
            self.logger.info(f"Workflow execution id: {workflow_execution_id}")
        # This is kinda WTF exception since create_workflow_execution shouldn't fail for manual
        except Exception as e:
            self.logger.error(f"WTF: error creating workflow execution: {e}")
            raise e
        self.logger.info(
            "Adding workflow to run",
            extra={
                "workflow_id": workflow_id,
                "workflow_execution_id": workflow_execution_id,
                "tenant_id": tenant_id,
                "triggered_by": "manual",
                "triggered_by_user": triggered_by_user,
            },
        )
        with self.lock:
            event.trigger = "manual"
            self.workflows_to_run.append(
                {
                    "workflow_id": workflow_id,
                    "workflow_execution_id": workflow_execution_id,
                    "tenant_id": tenant_id,
                    "triggered_by": "manual",
                    "triggered_by_user": triggered_by_user,
                    "event": event,
                    "retry": True,
                }
            )
        return workflow_execution_id

    def _get_unique_execution_number(self, fingerprint=None):
        """
        Translates the fingerprint to a unique execution number

        Returns:
            int: an int represents unique execution number
        """
        # if fingerprint supplied
        if fingerprint:
            payload = str(fingerprint).encode()
        # else, just return random
        else:
            payload = str(uuid.uuid4()).encode()
        return int(hashlib.sha256(payload).hexdigest(), 16) % (
            WorkflowScheduler.MAX_SIZE_SIGNED_INT + 1
        )

    def _timeout_workflows(self):
        """
        Record timeout for workflows that are running for too long.
        """
        workflow_executions = get_timeouted_workflow_exections()
        for workflow_execution in workflow_executions:
            self.logger.info(
                "Timeout workflow execution detected",
                extra={
                    "workflow_id": workflow_execution.workflow_id,
                    "workflow_execution_id": workflow_execution.id,
                    "tenant_id": workflow_execution.tenant_id,
                },
            )
            timeout_message = "Workflow execution timed out. "

            if RUNNING_IN_CLOUD_RUN:
                timeout_message += (
                    "Please contact Keep support for help with this issue."
                )
            else:
                timeout_message += (
                    "Most probably it's caused by worker restart or crash "
                    "during long workflow execution. Check backend logs."
                )

            self._finish_workflow_execution(
                tenant_id=workflow_execution.tenant_id,
                workflow_id=workflow_execution.workflow_id,
                workflow_execution_id=workflow_execution.id,
                status=WorkflowStatus.ERROR,
                error=timeout_message,
            )

    def _handle_event_workflows(self):
        # TODO - event workflows should be in DB too, to avoid any state problems.

        # take out all items from the workflows to run and run them, also, clean the self.workflows_to_run list
        with self.lock:
            workflows_to_run, self.workflows_to_run = self.workflows_to_run, []
        for workflow_to_run in workflows_to_run:
            self.logger.info(
                "Running event workflow on background",
                extra={
                    "workflow_id": workflow_to_run.get("workflow_id"),
                    "workflow_execution_id": workflow_to_run.get(
                        "workflow_execution_id"
                    ),
                    "tenant_id": workflow_to_run.get("tenant_id"),
                },
            )
            workflow = workflow_to_run.get("workflow")
            workflow_id = workflow_to_run.get("workflow_id")
            tenant_id = workflow_to_run.get("tenant_id")
            # Update queue size metrics
            workflow_queue_size.labels(tenant_id=tenant_id).set(
                len(self.workflows_to_run)
            )
            workflow_execution_id = workflow_to_run.get("workflow_execution_id")
            if not workflow:
                self.logger.info("Loading workflow")
                try:
                    workflow = self.workflow_store.get_workflow(
                        workflow_id=workflow_id, tenant_id=tenant_id
                    )
                # In case the provider are not configured properly
                except ProviderConfigurationException as e:
                    self.logger.error(
                        f"Error getting workflow: {e}",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_execution_id": workflow_execution_id,
                            "tenant_id": tenant_id,
                        },
                    )
                    self._finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        workflow_execution_id=workflow_execution_id,
                        status=WorkflowStatus.PROVIDERS_NOT_CONFIGURED,
                        error=f"Providers are not configured for workflow {workflow_id}, please configure it so Keep will be able to run it",
                    )
                    continue
                except Exception as e:
                    self.logger.error(
                        f"Error getting workflow: {e}",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_execution_id": workflow_execution_id,
                            "tenant_id": tenant_id,
                        },
                    )
                    self._finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        workflow_execution_id=workflow_execution_id,
                        status=WorkflowStatus.ERROR,
                        error=f"Error getting workflow: {e}",
                    )
                    continue

            event = workflow_to_run.get("event")

            triggered_by = workflow_to_run.get("triggered_by")
            if triggered_by == "manual":
                triggered_by_user = workflow_to_run.get("triggered_by_user")
                triggered_by = f"manually by {triggered_by_user}"
            elif triggered_by.startswith("incident:"):
                triggered_by = f"type:{triggered_by} name:{event.name} id:{event.id}"
            else:
                triggered_by = f"type:alert name:{event.name} id:{event.id}"

            if isinstance(event, IncidentDto):
                event_id = str(event.id)
                event_type = "incident"
                fingerprint = "incident:{}".format(event_id)
            else:
                event_id = event.event_id
                event_type = "alert"
                fingerprint = event.fingerprint

            # In manual, we create the workflow execution id sync so it could be tracked by the caller (UI)
            # In event (e.g. alarm), we will create it here
            if not workflow_execution_id:
                # creating the execution id here to be able to trace it in logs even in case of IntegrityError
                # eventually, workflow_execution_id == execution_id
                execution_id = str(uuid.uuid4())
                try:
                    # if the workflow can run in parallel, we just to create a some random execution number
                    if workflow.workflow_strategy == WorkflowStrategy.PARALLEL.value:
                        workflow_execution_number = self._get_unique_execution_number()
                    # else, we want to enforce that no workflow already run with the same fingerprint
                    else:
                        workflow_execution_number = self._get_unique_execution_number(
                            fingerprint
                        )
                    workflow_execution_id = create_workflow_execution(
                        workflow_id=workflow_id,
                        tenant_id=tenant_id,
                        triggered_by=triggered_by,
                        execution_number=workflow_execution_number,
                        fingerprint=fingerprint,
                        event_id=event_id,
                        execution_id=execution_id,
                        event_type=event_type,
                    )
                # If there is already running workflow from the same event
                except IntegrityError:
                    # if the strategy is with RETRY, just put a warning and add it back to the queue
                    if (
                        workflow.workflow_strategy
                        == WorkflowStrategy.NONPARALLEL_WITH_RETRY.value
                    ):
                        self.logger.info(
                            "Collision with workflow execution! will retry next time",
                            extra={
                                "workflow_id": workflow_id,
                                "tenant_id": tenant_id,
                            },
                        )
                        with self.lock:
                            self.workflows_to_run.append(
                                {
                                    "workflow_id": workflow_id,
                                    "workflow_execution_id": workflow_execution_id,
                                    "tenant_id": tenant_id,
                                    "triggered_by": triggered_by,
                                    "event": event,
                                    "retry": True,
                                }
                            )
                        continue
                    # else if NONPARALLEL, just finish the execution
                    elif (
                        workflow.workflow_strategy == WorkflowStrategy.NONPARALLEL.value
                    ):
                        self.logger.error(
                            "Collision with workflow execution! will not retry",
                            extra={
                                "workflow_id": workflow_id,
                                "tenant_id": tenant_id,
                            },
                        )
                        self._finish_workflow_execution(
                            tenant_id=tenant_id,
                            workflow_id=workflow_id,
                            workflow_execution_id=workflow_execution_id,
                            status=WorkflowStatus.ERROR,
                            error="Workflow already running with the same fingerprint",
                        )
                        continue
                    # else, just raise the exception (that should not happen)
                    else:
                        self.logger.exception("Collision with workflow execution!")
                        continue
                except Exception as e:
                    self.logger.error(f"Error creating workflow execution: {e}")
                    continue

            # if thats a retry, we need to re-pull the alert to update the enrichments
            # for example: 2 alerts arrived within a 0.1 seconds the first one is "firing" and the second one is "resolved"
            #               - the first alert will trigger a workflow that will create a ticket with "firing"
            #                    and enrich the alert with the ticket_url
            #               - the second one will wait for the next iteration
            #               - on the next iteratino, the second alert enriched with the ticket_url
            #                    and will trigger a workflow that will update the ticket with "resolved"
            if workflow_to_run.get("retry", False) and isinstance(event, AlertDto):
                try:
                    self.logger.info(
                        "Updating enrichments for workflow after retry",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_execution_id": workflow_execution_id,
                            "tenant_id": tenant_id,
                        },
                    )
                    new_enrichment = get_enrichment(
                        tenant_id, event.fingerprint, refresh=True
                    )
                    # merge the new enrichment with the original event
                    if new_enrichment:
                        new_event = event.dict()
                        new_event.update(new_enrichment.enrichments)
                        event = AlertDto(**new_event)
                    self.logger.info(
                        "Enrichments updated for workflow after retry",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_execution_id": workflow_execution_id,
                            "tenant_id": tenant_id,
                            "new_enrichment": new_enrichment,
                        },
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to get enrichment: {e}",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_execution_id": workflow_execution_id,
                            "tenant_id": tenant_id,
                        },
                    )
                    self._finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        workflow_execution_id=workflow_execution_id,
                        status=WorkflowStatus.ERROR,
                        error=f"Error getting alert by id: {e}",
                    )
                    continue
            # Last, run the workflow
            future = self.executor.submit(
                self._run_workflow,
                tenant_id,
                workflow_id,
                workflow,
                workflow_execution_id,
                event,
            )
            self.futures.add(future)
            future.add_done_callback(lambda f: self.futures.remove(f))

        self.logger.debug(
            "Event workflows handled",
            extra={"current_number_of_workflows": len(self.futures)},
        )

    def _start(self):
        RUN_TIMEOUT_CHECKS_EVERY = 100
        self.logger.info("Starting workflows scheduler")
        runs = 0
        while not self._stop:
            runs += 1
            # get all workflows that should run now
            self.logger.debug(
                "Starting workflow scheduler iteration",
                extra={"current_number_of_workflows": len(self.futures)},
            )
            try:
                self._handle_interval_workflows()
                self._handle_event_workflows()
                if runs % RUN_TIMEOUT_CHECKS_EVERY == 0:
                    self._timeout_workflows()
            except Exception:
                # This is the "mainloop" of the scheduler, we don't want to crash it
                # But any exception here should be investigated
                self.logger.exception("Error getting workflows that should run")
                pass
            self.logger.debug("Sleeping until next iteration")
            time.sleep(1)
        self.logger.info("Workflows scheduler stopped")

    def stop(self):
        self.logger.info("Stopping scheduled workflows")
        self._stop = True

        # Wait for scheduler to stop first
        if self.scheduler_future:
            try:
                self.scheduler_future.result(
                    timeout=5
                )  # Add timeout to prevent hanging
            except Exception:
                self.logger.exception("Error waiting for scheduler to stop")

        # Cancel all running workflows with timeout
        for future in list(self.futures):  # Create a copy of futures set
            try:
                self.logger.info("Cancelling future")
                future.cancel()
                future.result(timeout=1)  # Add timeout
                self.logger.info("Future cancelled")
            except Exception:
                self.logger.exception("Error cancelling future")

        # Shutdown the executor with timeout
        if self.executor:
            try:
                self.logger.info("Shutting down executor")
                self.executor.shutdown(wait=True, cancel_futures=True)
                self.executor = None
                self.logger.info("Executor shut down")
            except Exception:
                self.logger.exception("Error shutting down executor")

        self.futures.clear()
        self.logger.info("Scheduled workflows stopped")

    def _finish_workflow_execution(
        self,
        tenant_id: str,
        workflow_id: str,
        workflow_execution_id: str,
        status: WorkflowStatus,
        error=None,
    ):
        # mark the workflow execution as finished in the db
        finish_workflow_execution_db(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=workflow_execution_id,
            status=status.value,
            error=error,
        )

        if KEEP_EMAILS_ENABLED:
            # get the previous workflow execution id
            previous_execution = get_previous_execution_id(
                tenant_id, workflow_id, workflow_execution_id
            )
            # if error, send an email
            if status == WorkflowStatus.ERROR and (
                previous_execution
                is None  # this means this is the first execution, for example
                or previous_execution.status != WorkflowStatus.ERROR.value
            ):
                workflow = get_workflow_db(tenant_id=tenant_id, workflow_id=workflow_id)
                try:
                    keep_platform_url = config(
                        "KEEP_PLATFORM_URL", default="https://platform.keephq.dev"
                    )
                    error_logs_url = f"{keep_platform_url}/workflows/{workflow_id}/runs/{workflow_execution_id}"
                    self.logger.debug(
                        f"Sending email to {workflow.created_by} for failed workflow {workflow_id}"
                    )
                    email_sent = send_email(
                        to_email=workflow.created_by,
                        template_id=EmailTemplates.WORKFLOW_RUN_FAILED,
                        workflow_id=workflow_id,
                        workflow_name=workflow.name,
                        workflow_execution_id=workflow_execution_id,
                        error=error,
                        url=error_logs_url,
                    )
                    if email_sent:
                        self.logger.info(
                            f"Email sent to {workflow.created_by} for failed workflow {workflow_id}"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to send email to {workflow.created_by} for failed workflow {workflow_id}: {e}"
                    )
