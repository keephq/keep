import chevron

from keep.conditions.condition_factory import ConditionFactory
from keep.providers.base.base_provider import BaseProvider


class Step:
    def __init__(self, step_id, step_config, provider: BaseProvider):
        self.step_id = step_id
        self.step_config = step_config
        self.step_conditions = step_config.get("condition", [])
        self.step_conditions_results = {}
        self.provider = provider

    def run(self, context):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Run the step query
            parameters = self.provider.get_parameters()
            # Inject the context to the parameters
            for parameter in parameters:
                parameters[parameter] = self._inject_context_to_parameter(
                    parameters[parameter], context
                )

            step_output = self.provider.query(**parameters)
            context["steps"][self.step_id] = {"results": step_output}
            # this is an alias to the current step output
            context["steps"]["this"] = {"results": step_output}
            # Validate the step output
            self._post_step_validations(context)
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        pass

    def _post_step_validations(self, context):
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            condition = ConditionFactory.get_condition(condition_type, condition)
            condition_result = condition.apply(context)
            self.step_conditions_results[condition_type] = condition_result

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
