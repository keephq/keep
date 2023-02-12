import logging

import chevron

from keep.conditions.condition_factory import ConditionFactory
from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


class Step:
    def __init__(
        self, step_id, step_config, provider: BaseProvider, provider_parameters: dict
    ):
        self.step_id = step_id
        self.step_config = step_config
        self.step_conditions = step_config.get("condition", [])
        self.step_conditions_results = {}
        self.provider = provider
        self.provider_parameters = provider_parameters
        self.io_handler = IOHandler()
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager.get_instance()

    def run(self):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Inject the context to the parameters
            for parameter in self.provider_parameters:
                self.provider_parameters[parameter] = self._inject_context_to_parameter(
                    self.provider_parameters[parameter]
                )
            step_output = self.provider.query(**self.provider_parameters)
            self.context_manager.steps_context[self.step_id] = {"results": step_output}
            # this is an alias to the current step output
            self.context_manager.steps_context["this"] = {"results": step_output}
            # Validate the step output
            self._post_step_validations()
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        self.logger.debug("Pre step validation")
        self.logger.debug("Pre Step validation success")

    def _post_step_validations(self):
        self.logger.debug("Post step validation")
        foreach = self.step_config.get("foreach")
        if foreach:
            self._post_each_step_validations(foreach.get("value"))
        else:
            self._post_single_step_validations()
        self.logger.debug("Post Step validation success")

    def _post_each_step_validations(self, foreach_value_template):
        context = self.context_manager.get_full_context()
        foreach_actual_value = self._get_actual_value(foreach_value_template)
        for value in foreach_actual_value:
            # will be use inside the io handler
            self.context_manager.set_for_each_context(value)
            for condition in self.step_conditions:
                condition_type = condition.get("type")
                condition = ConditionFactory.get_condition(condition_type, condition)
                condition_what_to_compare = condition.get_what_to_compare()
                condition_compare_value = condition.get_compare_value()
                condition_result = condition.apply()
                self.context_manager.set_condition_results(
                    self.step_id,
                    condition_type,
                    value,
                    condition_compare_value,
                    condition_what_to_compare,
                    condition_result,
                )

    def _post_single_step_validations(self):
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            condition = ConditionFactory.get_condition(condition_type, condition)
            condition_what_to_compare = condition.get_what_to_compare()
            condition_compare_value = condition.get_compare_value()
            condition_result = condition.apply()
            self.context_manager.set_condition_results(
                self.step_id,
                condition_type,
                condition,
                condition_compare_value,
                condition_what_to_compare,
                condition_result,
            )
        self.logger.debug("Post Step validation success")

    def _get_actual_value(self, foreach_value_template):
        val = self.io_handler.render(foreach_value_template)
        return val

    @property
    def action_needed(self):
        # iterate over all conditions:
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            # for each condition, iterate over results
            for result in self.context_manager.steps_context[self.step_id][
                "conditions"
            ][condition_type]:
                # if any of the results is true, then action should be run
                if result.get("result"):
                    return True
        # All conditions does not apply
        return False

    def _inject_context_to_parameter(self, template):
        context = self.context_manager.get_full_context()
        return chevron.render(template, context)

    @property
    def failure_strategy(self):
        return self.step_config.get("failure_strategy")


class StepError(Exception):
    pass
