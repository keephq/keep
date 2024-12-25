import asyncio
import enum
import hashlib
import logging
import queue
import threading
import typing
import uuid
from threading import Lock

from sqlalchemy.exc import IntegrityError

from keep.api.core.config import config
from keep.api.core.db import create_workflow_execution
from keep.api.core.db import finish_workflow_execution as finish_workflow_execution_db
from keep.api.core.db import get_enrichment, get_previous_execution_id
from keep.api.core.db import get_workflow as get_workflow_db
from keep.api.core.db import get_workflows_that_should_run
from keep.api.models.alert import AlertDto, IncidentDto
from keep.api.utils.email_utils import KEEP_EMAILS_ENABLED, EmailTemplates, send_email
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow, WorkflowStrategy
from keep.workflowmanager.workflowstore import WorkflowStore

READ_ONLY_MODE = config("KEEP_READ_ONLY", default="false") == "true"


class WorkflowStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    PROVIDERS_NOT_CONFIGURED = "providers_not_configured"


class WorkflowScheduler:
    MAX_SIZE_SIGNED_INT = 2147483647

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
        self.task = None

    async def start(self, loop=None):
        self.logger.info("Starting workflows scheduler")
        # Shahar: fix for a bug in unit tests
        self._stop = False
        if loop is None:
            loop = asyncio.get_running_loop()
        self.task = loop.create_task(self._start())
        self.logger.info("Workflows scheduler started")

    async def _handle_interval_workflows(self):
        workflows = []

        if not self.interval_enabled:
            self.logger.debug("Interval workflows are disabled")
            return

        try:
            # get all workflows that should run due to interval
            workflows = await get_workflows_that_should_run()
        except Exception:
            self.logger.exception("Error getting workflows that should run")
            pass
        for workflow in workflows:
            self.logger.debug("Running workflow on background")

            workflow_execution_id = workflow.get("workflow_execution_id")
            tenant_id = workflow.get("tenant_id")
            workflow_id = workflow.get("workflow_id")
            try:
                workflow = await self.workflow_store.get_workflow(tenant_id, workflow_id)
            except ProviderConfigurationException:
                self.logger.exception(
                    "Provider configuration is invalid",
                    extra={
                        "workflow_id": workflow_id,
                        "workflow_execution_id": workflow_execution_id,
                        "tenant_id": tenant_id,
                    },
                )
                await self._finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    workflow_execution_id=workflow_execution_id,
                    status=WorkflowStatus.PROVIDERS_NOT_CONFIGURED,
                    error=f"Providers are not configured for workflow {workflow_id}, please configure it so Keep will be able to run it",
                )
                continue
            except Exception as e:
                self.logger.error(f"Error getting workflow: {e}")
                await self._finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    workflow_execution_id=workflow_execution_id,
                    status=WorkflowStatus.ERROR,
                    error=f"Error getting workflow: {e}",
                )
                continue
            await asyncio.create_task(self._run_workflow(tenant_id, workflow_id, workflow, workflow_execution_id))

    async def _run_workflow(
        self,
        tenant_id,
        workflow_id,
        workflow: Workflow,
        workflow_execution_id: str,
        event_context=None,
    ):
        if READ_ONLY_MODE:
            # This is because sometimes workflows takes 0 seconds and the executions chart is not updated properly.
            self.logger.debug("Sleeping for 3 seconds in favor of read only mode")
            await asyncio.sleep(3)
        self.logger.info(f"Running workflow {workflow.workflow_id}...")

        try:
            if isinstance(event_context, AlertDto):
                # set the event context, e.g. the event that triggered the workflow
                workflow.context_manager.set_event_context(event_context)
            else:
                # set the incident context, e.g. the incident that triggered the workflow
                workflow.context_manager.set_incident_context(event_context)

            errors, _ = await self.workflow_manager._run_workflow(
                workflow, workflow_execution_id
            )
        except Exception as e:
            self.logger.exception(f"Failed to run workflow {workflow.workflow_id}...")
            await self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.ERROR,
                error=str(e),
            )
            return

        if any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
            await self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.ERROR,
                error="\n".join(str(e) for e in errors),
            )
        else:
            await self._finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_execution_id=workflow_execution_id,
                status=WorkflowStatus.SUCCESS,
                error=None,
            )
        self.logger.info(f"Workflow {workflow.workflow_id} ran")
        return True

    async def handle_workflow_test(self, workflow, tenant_id, triggered_by_user):

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
                result_queue.put((str(e), None))

        thread = threading.Thread(
            target=run_workflow_wrapper,
            args=[
                self.workflow_manager._run_workflow,
                workflow,
                workflow_execution_id,
                True,
                result_queue,
            ],
        )
        thread.start()
        thread.join()
        errors, results = result_queue.get()

        self.logger.info(
            f"Workflow {workflow.workflow_id} ran",
            extra={"errors": errors, "results": results},
        )

        status = "success"
        error = None
        if any(errors):
            error = "\n".join(str(e) for e in errors)
            status = "error"

        return {
            "workflow_execution_id": workflow_execution_id,
            "status": status,
            "error": error,
            "results": results,
        }

    async def handle_manual_event_workflow(
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

            workflow_execution_id = await create_workflow_execution(
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

    async def _handle_event_workflows(self):
        # TODO - event workflows should be in DB too, to avoid any state problems.

        # take out all items from the workflows to run and run them, also, clean the self.workflows_to_run list
        tasks = []
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
            workflow_execution_id = workflow_to_run.get("workflow_execution_id")
            if not workflow:
                self.logger.info("Loading workflow")
                try:
                    workflow = await self.workflow_store.get_workflow(
                        workflow_id=workflow_id, tenant_id=tenant_id
                    )
                # In case the provider are not configured properly
                except ProviderConfigurationException as e:
                    self.logger.error(f"Error getting workflow: {e}")
                    await self._finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        workflow_execution_id=workflow_execution_id,
                        status=WorkflowStatus.PROVIDERS_NOT_CONFIGURED,
                        error=f"Providers are not configured for workflow {workflow_id}, please configure it so Keep will be able to run it",
                    )
                    continue
                except Exception as e:
                    self.logger.error(f"Error getting workflow: {e}")
                    await self._finish_workflow_execution(
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
                    workflow_execution_id = await create_workflow_execution(
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
                        await self._finish_workflow_execution(
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
                    await self._finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        workflow_execution_id=workflow_execution_id,
                        status=WorkflowStatus.ERROR,
                        error=f"Error getting alert by id: {e}",
                    )
                    continue
            tasks.append(asyncio.create_task(self._run_workflow(tenant_id, workflow_id, workflow, workflow_execution_id, event)))
            await asyncio.gather(*tasks)


    async def _start(self):
        self.logger.info("Starting workflows scheduler")
        while not self._stop:
            # get all workflows that should run now
            self.logger.debug("Getting workflows that should run...")
            try:
                await self._handle_interval_workflows()
                await self._handle_event_workflows()
            except Exception:
                # This is the "mainloop" of the scheduler, we don't want to crash it
                # But any exception here should be investigated
                self.logger.exception("Error getting workflows that should run")
                pass
            self.logger.debug("Sleeping until next iteration")
            await asyncio.sleep(1)
        self.logger.info("Workflows scheduler stopped")

    async def run_workflows(self, workflows: typing.List[Workflow]):
        for workflow in workflows:
            asyncio.create_task(self._run_workflows_with_interval(workflow))
        # as long as the stop flag is not set, sleep
        while not self._stop:
            await asyncio.sleep(1)

    async def stop(self):
        self.logger.info("Stopping scheduled workflows")
        self._stop = True
        if self.task is not None:
            await self.task
        self.logger.info("Scheduled workflows stopped")

    async def _run_workflows_with_interval(
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
                await self.workflow_manager._run_workflow(workflow, uuid.uuid4())
            except Exception:
                self.logger.exception(
                    f"Failed to run workflow {workflow.workflow_id}..."
                )
            self.logger.info(f"Workflow {workflow.workflow_id} ran")
            if workflow.workflow_interval > 0:
                self.logger.info(
                    f"Sleeping for {workflow.workflow_interval} seconds..."
                )
                await asyncio.sleep(workflow.workflow_interval)
            else:
                self.logger.info("Workflow will not run again")
                break

    async def _finish_workflow_execution(
        self,
        tenant_id: str,
        workflow_id: str,
        workflow_execution_id: str,
        status: WorkflowStatus,
        error=None,
    ):
        # mark the workflow execution as finished in the db
        await finish_workflow_execution_db(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=workflow_execution_id,
            status=status.value,
            error=error,
        )

        if KEEP_EMAILS_ENABLED:
            # get the previous workflow execution id
            previous_execution = await get_previous_execution_id(
                tenant_id, workflow_id, workflow_execution_id
            )
            # if error, send an email
            if status == WorkflowStatus.ERROR and (
                previous_execution
                is None  # this means this is the first execution, for example
                or previous_execution.status != WorkflowStatus.ERROR.value
            ):
                workflow = await get_workflow_db(tenant_id=tenant_id, workflow_id=workflow_id)
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
