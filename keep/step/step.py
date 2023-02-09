import logging

import chevron

from keep.conditions.condition_factory import ConditionFactory
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
        self.logger = logging.getLogger(__name__)

    def run(self, context):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Inject the context to the parameters
            for parameter in self.provider_parameters:
                self.provider_parameters[parameter] = self._inject_context_to_parameter(
                    self.provider_parameters[parameter], context
                )
            step_output = self.provider.query(**self.provider_parameters)
            context["steps"][self.step_id] = {"results": step_output}
            # this is an alias to the current step output
            context["steps"]["this"] = {"results": step_output}
            # Validate the step output
            self._post_step_validations(context)
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        self.logger.debug("Pre step validation")
        self.logger.debug("Pre Step validation success")

    def _post_step_validations(self, context):
        self.logger.debug("Post step validation")
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            condition = ConditionFactory.get_condition(condition_type, condition)
            condition_result = condition.apply(context)
            self.step_conditions_results[condition_type] = condition_result
        self.logger.debug("Post Step validation success")

    @property
    def action_needed(self):
        # if one of the conditions is , then action is needed
        for result in self.step_conditions_results.values():
            if result:
                return True
        # All conditions does not apply
        return False

    def _inject_context_to_parameter(self, template, context):
        return chevron.render(template, context)

    @property
    def failure_strategy(self):
        return self.step_config.get("failure_strategy")


class StepError(Exception):
    pass
