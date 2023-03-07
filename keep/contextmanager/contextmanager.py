import os
from typing import Self

import click


class ContextManager:
    __instance = None

    # https://stackoverflow.com/questions/36286894/name-not-defined-in-type-annotation
    @staticmethod
    def get_instance() -> "ContextManager":
        if ContextManager.__instance == None:
            ContextManager()
        return ContextManager.__instance

    def __init__(self):
        if ContextManager.__instance != None:
            raise Exception(
                "Singleton class is a singleton class and cannot be instantiated more than once."
            )
        else:
            ContextManager.__instance = self

        self._steps_context = {}
        self.providers_context = {}
        self.alert_context = {}
        self.foreach_context = {}
        try:
            self.click_context = click.get_current_context()
        except RuntimeError:
            self.click_context = {}
        self.aliases = {}

    # TODO - If we want to support multiple alerts at once we need to change this
    def set_alert_context(self, alert_context):
        self.alert_context = alert_context

    def get_alert_id(self):
        return self.alert_context.get("alert_id")

    def get_full_context(self):
        full_context = {
            "providers": self.providers_context,
            "steps": self._steps_context,
            "foreach": {"value": self.foreach_context},
            "env": os.environ,
        }
        full_context.update(self.aliases)
        return full_context

    def set_for_each_context(self, value):
        self.foreach_context = value

    def set_condition_results(
        self,
        step_id,
        condition_type,
        compare_to,
        compare_value,
        result,
        condition_alias=None,
        raw_value=None,
    ):
        """_summary_

        Args:
            step_id (_type_): id of the step
            condition_type (_type_): type of the condition
            compare_to (_type_): _description_
            compare_value (_type_): _description_
            result (_type_): _description_
            condition_alias (_type_, optional): _description_. Defaults to None.
            raw_value (_type_): the raw value which the condition was compared to. this is relevant only for foreach conditions
        """
        if step_id not in self._steps_context:
            self._steps_context[step_id] = {"conditions": [], "results": {}}
        if "conditions" not in self._steps_context[step_id]:
            self._steps_context[step_id]["conditions"] = []

        self._steps_context[step_id]["conditions"].append(
            {
                "raw_value": raw_value,
                "value": compare_value,
                "compare_to": compare_to,
                "result": result,
                "condition_type": condition_type,
                "condition_alias": condition_alias,
            }
        )
        if condition_alias:
            self.aliases[condition_alias] = result

    def get_actionable_results(self):
        actionable_results = []
        for step_id in self._steps_context:
            if "conditions" in self._steps_context[step_id]:
                for condition in self._steps_context[step_id]["conditions"]:
                    if condition["result"] == True:
                        actionable_results.append(condition)
        return actionable_results

    def set_step_context(self, step_id, results):
        if step_id not in self._steps_context:
            self._steps_context[step_id] = {"conditions": [], "results": {}}
        self._steps_context[step_id]["results"] = results
        # this is an alias to the current step output
        self._steps_context["this"] = self._steps_context[step_id]

    def load_step_context(self, step_id, step_results, step_conditions):
        """Load a step context

        Args:
            step_id (_type_): _description_
            step_results (_type_): _description_
            step_conditions (_type_): _description_

        Returns:
            _type_: _description_
        """
        self._steps_context[step_id] = {"results": step_results}
        for condition in step_conditions:
            self.set_condition_results(
                step_id,
                condition["condition_type"],
                condition["raw_value"],
                condition["compare_to"],
                condition["value"],
                condition["result"],
                condition.get("alias"),
            )
        return True

    # TODO - add step per alert?
    def get_step_context(self, step_id):
        return {"step_id": step_id, "step_context": self._steps_context.get(step_id)}
