import json
import os

import click
from starlette_context import context


def get_context_manager_id():
    try:
        # If we are running as part of FastAPI, we need context_manager per request
        request_id = context.data.get("X-Request-ID")
        return request_id
    except:
        return "main"


class ContextManager:
    STATE_FILE = "keepstate.json"
    __instances = {}

    # https://stackoverflow.com/questions/36286894/name-not-defined-in-type-annotation
    @staticmethod
    def get_instance() -> "ContextManager":
        context_manager_id = get_context_manager_id()
        if context_manager_id not in ContextManager.__instances:
            ContextManager.__instances[context_manager_id] = ContextManager()
        return ContextManager.__instances[context_manager_id]

    @staticmethod
    def delete_instance():
        context_manager_id = get_context_manager_id()
        if context_manager_id in ContextManager.__instances:
            del ContextManager.__instances[context_manager_id]

    def __init__(self):
        context_manager_id = get_context_manager_id()
        if context_manager_id in ContextManager.__instances:
            raise Exception(
                "Singleton class is a singleton class and cannot be instantiated more than once."
            )
        else:
            ContextManager.__instances[context_manager_id] = self

        self.state_file = self.STATE_FILE or os.environ.get("KEEP_STATE_FILE")
        self.steps_context = {}
        self.providers_context = {}
        self.alert_context = {}
        self.foreach_context = {}
        self.foreach_conditions = []
        self.foreach_index = None
        try:
            self.click_context = click.get_current_context()
        except RuntimeError:
            self.click_context = {}
        self.aliases = {}
        self.state = {}
        self.__load_state()

    # TODO - If we want to support multiple alerts at once we need to change this
    def set_alert_context(self, alert_context):
        self.alert_context = alert_context

    def get_alert_id(self):
        return self.alert_context.get("alert_id")

    def get_full_context(self, exclude_state=False):
        """
        Gets full context on the alerts

        Usage: context injection used, for example, in iohandler

        Args:
            exclude_state (bool, optional): for instance when dumping the context to state file, you don't want to dump previous state
                it's already there. Defaults to False.

        Returns:
            dict: dictinoary contains all context about this alert
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
            "providers": self.providers_context,
            "steps": self.steps_context,
            # This is a hack to support both "before condition" and "after condition"
            # TODO - fix it and make it more elegant - see the func docs
            "foreach": self.foreach_context
            if "value" in self.foreach_context
            else {"value": self.foreach_context},
            "env": os.environ,
        }

        if not exclude_state:
            full_context["state"] = self.state

        full_context.update(self.aliases)
        return full_context

    def set_for_each_context(self, value):
        self.foreach_context = value

    def set_condition_results(
        self,
        step_id,
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
            step_id (_type_): id of the step
            condition_type (_type_): type of the condition
            compare_to (_type_): _description_
            compare_value (_type_): _description_
            result (_type_): _description_
            condition_alias (_type_, optional): _description_. Defaults to None.
            value (_type_): the raw value which the condition was compared to. this is relevant only for foreach conditions
        """
        if step_id not in self.steps_context:
            self.steps_context[step_id] = {"conditions": {}, "results": {}}
        if "conditions" not in self.steps_context[step_id]:
            self.steps_context[step_id]["conditions"] = {condition_name: []}
        if condition_name not in self.steps_context[step_id]["conditions"]:
            self.steps_context[step_id]["conditions"][condition_name] = []

        self.steps_context[step_id]["conditions"][condition_name].append(
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
        if condition_alias:
            self.aliases[condition_alias] = result

    def get_actionable_results(self):
        actionable_results = []
        for step_id in self.steps_context:
            # TODO: more robust way to identify the alias
            if step_id == "this":
                continue
            if "conditions" in self.steps_context[step_id]:
                # TODO: more robust way to identify actionable results
                # TODO: support multiple conditions
                for condition in self.steps_context[step_id]["conditions"]:
                    for condition_result in self.steps_context[step_id]["conditions"][
                        condition
                    ]:
                        if condition_result["result"] == True:
                            actionable_results.append(condition_result)
        return actionable_results

    def set_step_context(self, step_id, results):
        if step_id not in self.steps_context:
            self.steps_context[step_id] = {"conditions": {}, "results": {}}
        self.steps_context[step_id]["results"] = results
        # this is an alias to the current step output
        self.steps_context["this"] = self.steps_context[step_id]

    def load_step_context(self, step_id, step_results, step_conditions):
        """Load a step context

        Args:
            step_id (_type_): _description_
            step_results (_type_): _description_
            step_conditions (_type_): _description_

        Returns:
            _type_: _description_
        """
        self.steps_context[step_id] = {"results": step_results}
        for condition in step_conditions:
            self.set_condition_results(
                step_id,
                condition["name"],
                condition["type"],
                condition["compare_to"],
                condition["value"],
                condition["result"],
                condition_alias=condition.get("alias"),
                value=condition.get("value"),
            )
        return True

    # TODO - add step per alert?
    def get_step_context(self, step_id):
        return {"step_id": step_id, "step_context": self.steps_context.get(step_id)}

    def __load_state(self):
        if self.state_file:
            # TODO - SQLite
            try:
                with open(self.state_file, "r") as f:
                    self.state = json.load(f)
            except:
                self.state = {}

    def get_last_alert_run(self, alert_id):
        if alert_id in self.state:
            return self.state[alert_id][-1]
        # no previous runs
        else:
            return {}

    def set_last_alert_run(self, alert_id, alert_context, alert_status):
        # TODO - SQLite
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except:
            state = {alert_id: []}
        if alert_id not in state:
            state[alert_id] = []
        state[alert_id].append(
            {
                "alert_status": alert_status,
                "alert_context": alert_context,
            }
        )
        with open(self.state_file, "w") as f:
            json.dump(state, f, default=None)
