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

        self.steps_context = {}
        self.providers_context = {}
        self.alert_context = {}
        self.foreach_context = {}
        self.aliases = {}
        self.click_context = click.get_current_context()

    # TODO - If we want to support multiple alerts at once we need to change this
    def set_alert_context(self, alert_context):
        self.alert_context = alert_context

    def get_alert_id(self):
        return self.alert_context.get("alert_id")

    def get_full_context(self):
        full_context = {
            "providers": self.providers_context,
            "steps": self.steps_context,
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
        raw_value,
        compare_to,
        compare_value,
        result,
        condition_alias=None,
    ):
        if step_id not in self.steps_context:
            self.steps_context[step_id] = {"conditions": {}, "results": {}}
        if "conditions" not in self.steps_context[step_id]:
            self.steps_context[step_id]["conditions"] = []

        self.steps_context[step_id]["conditions"].append(
            {
                "raw_value": raw_value,
                "value": compare_value,
                "compare_to": compare_to,
                "result": result,
                "condition_type": condition_type,
            }
        )
        if condition_alias:
            self.aliases[condition_alias] = result

    def get_actionable_results(self):
        actionable_results = []
        for step_id in self.steps_context:
            if "conditions" in self.steps_context[step_id]:
                for condition_type in self.steps_context[step_id]["conditions"]:
                    for condition in self.steps_context[step_id]["conditions"][
                        condition_type
                    ]:
                        if condition["result"] == True:
                            actionable_results.append(
                                {
                                    "step_id": step_id,
                                    "condition_type": condition_type,
                                    "condition": condition,
                                }
                            )
        return actionable_results
