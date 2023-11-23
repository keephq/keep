# TODO - refactor context manager to support multitenancy in a more robust way
import json
import logging
import os

import click
from pympler.asizeof import asizeof

from keep.api.core.db import get_session
from keep.api.logging import WorkflowLoggerAdapter
from keep.storagemanager.storagemanagerfactory import StorageManagerFactory


class ContextManager:
    STATE_FILE = "keepstate.json"

    def __init__(
        self, tenant_id, workflow_id=None, workflow_execution_id=None, load_state=True
    ):
        self.logger = logging.getLogger(__name__)
        self.logger_adapter = WorkflowLoggerAdapter(
            self.logger, self, tenant_id, workflow_id, workflow_execution_id
        )
        self.workflow_id = workflow_id
        self.tenant_id = tenant_id
        self.storage_manager = StorageManagerFactory.get_file_manager()
        self.state_file = os.environ.get("KEEP_STATE_FILE") or self.STATE_FILE
        self.steps_context = {}
        self.steps_context_size = 0
        self.providers_context = {}
        self.event_context = {}
        self.foreach_context = {
            "value": None,
        }
        try:
            self.click_context = click.get_current_context()
        except RuntimeError:
            self.click_context = {}
        self.aliases = {}
        self.state = {}
        # dependencies are used so iohandler will be able to use the output class of the providers
        # e.g. let's say bigquery_provider results are google.cloud.bigquery.Row
        #     and we want to use it in iohandler, we need to import it before the eval
        self.dependencies = set()
        if load_state:
            self.__load_state()
        self.workflow_execution_id = None
        self._api_key = None

    @property
    def api_key(self):
        # avoid circular import
        from keep.api.utils.tenant_utils import get_or_create_api_key

        if self._api_key is None:
            session = next(get_session())
            self._api_key = get_or_create_api_key(
                session=session,
                tenant_id=self.tenant_id,
                unique_api_key_id="webhook",
            )
            session.close()
        return self._api_key

    def set_execution_context(self, workflow_execution_id):
        self.workflow_execution_id = workflow_execution_id
        self.logger_adapter.workflow_execution_id = workflow_execution_id

    def get_logger(self):
        return self.logger_adapter

    def set_event_context(self, event):
        self.event_context = event

    def get_workflow_id(self):
        return self.workflow_id

    def get_full_context(
        self, exclude_state=False, exclude_providers=False, exclude_env=False
    ):
        """
        Gets full context on the workflows

        Usage: context injection used, for example, in iohandler

        Args:
            exclude_state (bool, optional): for instance when dumping the context to state file, you don't want to dump previous state
                it's already there. Defaults to False.

        Returns:
            dict: dictinoary contains all context about this workflow
                  providers - all context about providers (configuration, etc)
                  steps - all context about steps (output, conditions, etc)
                  foreach - all context about the current 'foreach'
                            foreach can be in two modes:
                                1. "step foreach" - for step result
                                2. "condition foreach" - for each condition result
                            whereas in (2), the {{ foreach.value }} contains (1), in the (1) case, we need to explicitly put in under (value)
                            anyway, this should be refactored to something more structured
        """
        full_context = {
            "steps": self.steps_context,
            "foreach": self.foreach_context,
            "event": self.event_context,
            "alert": self.event_context,  # this is an alias so workflows will be able to use alert.source
        }

        if not exclude_providers:
            full_context["providers"] = self.providers_context

        if not exclude_state:
            full_context["state"] = self.state

        if not exclude_env:
            full_context["env"] = os.environ

        full_context.update(self.aliases)
        return full_context

    def set_for_each_context(self, value):
        self.foreach_context["value"] = value

    def set_condition_results(
        self,
        action_id,
        condition_name,
        condition_type,
        compare_to,
        compare_value,
        result,
        condition_alias=None,
        value=None,
        **kwargs,
    ):
        """_summary_

        Args:
            action_id (_type_): id of the step
            condition_type (_type_): type of the condition
            compare_to (_type_): _description_
            compare_value (_type_): _description_
            result (_type_): _description_
            condition_alias (_type_, optional): _description_. Defaults to None.
            value (_type_): the raw value which the condition was compared to. this is relevant only for foreach conditions
        """
        if action_id not in self.steps_context:
            self.steps_context[action_id] = {"conditions": {}, "results": {}}
        if "conditions" not in self.steps_context[action_id]:
            self.steps_context[action_id]["conditions"] = {condition_name: []}
        if condition_name not in self.steps_context[action_id]["conditions"]:
            self.steps_context[action_id]["conditions"][condition_name] = []

        self.steps_context[action_id]["conditions"][condition_name].append(
            {
                "value": value,
                "compare_value": compare_value,
                "compare_to": compare_to,
                "result": result,
                "type": condition_type,
                "alias": condition_alias,
                **kwargs,
            }
        )
        # update the current for each context
        self.foreach_context.update(
            {"compare_value": compare_value, "compare_to": compare_to, **kwargs}
        )
        if condition_alias:
            self.aliases[condition_alias] = result

    def set_step_provider_paremeters(self, step_id, provider_parameters):
        if step_id not in self.steps_context:
            self.steps_context[step_id] = {"provider_parameters": {}, "results": []}
        self.steps_context[step_id]["provider_parameters"] = provider_parameters

    def set_step_context(self, step_id, results, foreach=False):
        if step_id not in self.steps_context:
            self.steps_context[step_id] = {"provider_parameters": {}, "results": []}

        # If this is a foreach step, we need to append the results to the list
        # so we can iterate over them
        if foreach:
            self.steps_context[step_id]["results"].append(results)
        else:
            self.steps_context[step_id]["results"] = results
        # this is an alias to the current step output
        self.steps_context["this"] = self.steps_context[step_id]
        self.steps_context_size = asizeof(self.steps_context)

    def __load_state(self):
        try:
            self.state = json.loads(
                self.storage_manager.get_file(
                    self.tenant_id, self.state_file, create_if_not_exist=True
                )
            )
        except Exception as exc:
            self.logger.warning("Failed to load state file, using empty state")
            self.logger.warning(
                f"State storage: {self.storage_manager.__class__.__name__}"
            )
            self.logger.warning(f"Reason: {exc}")
            self.state = {}

    def get_last_workflow_run(self, workflow_id):
        if workflow_id in self.state:
            return self.state[workflow_id][-1]
        # no previous runs
        else:
            return {}

    def dump(self):
        self.logger.info("Dumping state file")
        # Write the updated state back to the file
        try:
            self.storage_manager.store_file(self.tenant_id, self.state_file, self.state)
        except Exception as e:
            self.logger.error(
                "Failed to dump state file",
                extra={"exception": e},
            )
            # TODO - should we raise an exception here?
        # dump the workflow logs to the db
        try:
            self.logger_adapter.dump()
        except Exception as e:
            # TODO - should be handled
            self.logger.error(
                "Failed to dump workflow logs",
                extra={"exception": e},
            )
        self.logger.info("State file dumped")

    def set_last_workflow_run(self, workflow_id, workflow_context, workflow_status):
        # TODO - SQLite
        self.logger.debug(
            "Adding workflow to state",
            extra={
                "workflow_id": workflow_id,
            },
        )
        if workflow_id not in self.state:
            self.state[workflow_id] = []
        self.state[workflow_id].append(
            {
                "workflow_status": workflow_status,
                "workflow_context": workflow_context,
            }
        )
        self.logger.debug(
            "Added workflow to state",
            extra={
                "workflow_id": workflow_id,
            },
        )
