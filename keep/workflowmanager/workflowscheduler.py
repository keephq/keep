import hashlib
import json
import logging
import threading
import time
import typing
import uuid

from sqlalchemy.exc import IntegrityError

from keep.api.core.db import (
    create_workflow_execution,
    finish_workflow_execution,
    get_workflows_that_should_run,
)
from keep.providers.providers_factory import ProviderConfigurationException
from keep.workflowmanager.workflow import Workflow
from keep.workflowmanager.workflowstore import WorkflowStore


class WorkflowScheduler:
    MAX_SIZE_SIGNED_INT = 2147483647

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
            except ProviderConfigurationException as e:
                self.logger.error(f"Provider configuration is invalid: {e}")
                finish_workflow_execution(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    execution_id=workflow_execution_id,
                    status="providers_not_configured",
                    error=f"Providers are not configured for workflow {workflow_id}, please configure it so Keep will be able to run it",
                )
                continue
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
            errors = self.workflow_manager._run_workflow(
                workflow, workflow_execution_id
            )
        except Exception as e:
            self.logger.exception(f"Failed to run workflow {workflow.workflow_id}...")
            finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                execution_id=workflow_execution_id,
                status="error",
                error=str(e),
            )
            return

        if any(errors):
            self.logger.info(msg=f"Workflow {workflow.workflow_id} ran with errors")
            finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                execution_id=workflow_execution_id,
                status="error",
                error=",".join(str(e) for e in errors),
            )
        else:
            finish_workflow_execution(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                execution_id=workflow_execution_id,
                status="success",
                error=None,
            )
        self.logger.info(f"Workflow {workflow.workflow_id} ran")

    def handle_manual_event_workflow(
        self, workflow_id, tenant_id, triggered_by_user, triggered, event
    ):
        try:
            # if the event is not defined, add some entropy
            if not event:
                event = {
                    "workflow_id": workflow_id,
                    "triggered_by_user": triggered_by_user,
                    "trigger": "manual",
                    "time": time.time(),
                }
            else:
                # so unique_execution_number will be different
                event["time"] = time.time()
            unique_execution_number = self._get_unique_execution_number(
                json.dumps(event).encode()
            )
            workflow_execution_id = create_workflow_execution(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                triggered_by=f"manually by {triggered_by_user}",
                execution_number=unique_execution_number,
            )
        # This is kinda WTF exception since create_workflow_execution shouldn't fail for manual
        except Exception as e:
            self.logger.error(f"WTF: error creating workflow execution: {e}")
            raise e
        self.workflows_to_run.append(
            {
                "workflow_id": workflow_id,
                "workflow_execution_id": workflow_execution_id,
                "tenant_id": tenant_id,
                "triggered_by": "manual",
                "triggered_by_user": triggered_by_user,
                "event": event,
            }
        )
        return workflow_execution_id

    def _get_unique_execution_number(self, payload: bytes):
        """Gets a unique execution number for a workflow execution
        # TODO: this is a hack. the execution number is a way to enforce that
        #       the interval mechanism will work. we need to find a better way to do it
        #       the "correct way" should be to seperate the interval mechanism from the event/manual mechanishm

        Args:
            workflow_id (str): the id of the workflow
            tenant_id (str): the id ot the tenant
            payload (bytes): some encoded binary payload

        Returns:
            int: an int represents unique execution number
        """
        return int(hashlib.sha256(payload).hexdigest(), 16) % (
            WorkflowScheduler.MAX_SIZE_SIGNED_INT + 1
        )

    def _handle_event_workflows(self):
        # TODO - event workflows should be in DB too, to avoid any state problems.

        # take out all items from the workflows to run and run them, also, clean the self.workflows_to_run list
        workflows_to_run, self.workflows_to_run = self.workflows_to_run, []
        for workflow_to_run in workflows_to_run:
            self.logger.info("Running event workflow on background")
            workflow = workflow_to_run.get("workflow")
            workflow_id = workflow_to_run.get("workflow_id")
            tenant_id = workflow_to_run.get("tenant_id")
            workflow_execution_id = workflow_to_run.get("workflow_execution_id")
            if not workflow:
                self.logger.info("Loading workflow")
                try:
                    workflow = self.workflow_store.get_workflow(
                        workflow_id=workflow_id, tenant_id=tenant_id
                    )
                # In case the provider are not configured properly
                except ProviderConfigurationException as e:
                    self.logger.error(f"Error getting workflow: {e}")
                    finish_workflow_execution(
                        tenant_id=tenant_id,
                        workflow_id=workflow_id,
                        execution_id=workflow_execution_id,
                        status="providers_not_configured",
                        error=f"Providers are not configured for workflow {workflow_id}, please configure it so Keep will be able to run it",
                    )
                    continue
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

            event = workflow_to_run.get("event")
            triggered_by = workflow_to_run.get("triggered_by")
            if triggered_by == "manual":
                triggered_by_user = workflow_to_run.get("triggered_by_user")
                triggered_by = f"manually by {triggered_by_user}"
            else:
                triggered_by = f"type:alert name:{event.name} id:{event.id}"

            # In manual, we create the workflow execution id sync so it could be tracked by the caller (UI)
            # In event (e.g. alarm), we will create it here
            # TODO: one more robust way to do it
            if not workflow_execution_id:
                try:
                    workflow_execution_number = self._get_unique_execution_number(
                        event.json().encode()
                    )
                    workflow_execution_id = create_workflow_execution(
                        workflow_id=workflow_id,
                        tenant_id=tenant_id,
                        triggered_by=triggered_by,
                        execution_number=workflow_execution_number,
                    )
                # This is kinda wtf exception since create workflow execution shouldn't fail for events other than interval
                except IntegrityError:
                    self.logger.exception(
                        "Collision with workflow execution! will retry next time"
                    )
                    continue
                except Exception as e:
                    self.logger.error(f"Error creating workflow execution: {e}")
                    continue
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
            self.logger.debug("Getting workflows that should run...")
            try:
                self._handle_interval_workflows()
                self._handle_event_workflows()
            except Exception as e:
                # This is the "mainloop" of the scheduler, we don't want to crash it
                # But any exception here should be investigated
                self.logger.error(f"Error getting workflows that should run: {e}")
                pass
            self.logger.debug("Sleeping until next iteration")
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
                self.workflow_manager._run_workflow(workflow, uuid.uuid4())
            except Exception:
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
