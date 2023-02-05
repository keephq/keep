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
            step_output = self.provider.query(context)
            # Validate the step output
            self._post_step_validations(context, step_output)
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        pass

    def _post_step_validations(self, context, step_output):
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            condition = ConditionFactory.get_condition(condition_type, condition)
            condition_result = condition.apply(context, step_output)
            self.step_conditions_results[condition_type] = condition_result

    @property
    def action_needed(self):
        # if one of the conditions is , then action is needed
        for result in self.step_conditions_results.values():
            if result:
                return True
        # All conditions does not apply
        return False


class StepError(Exception):
    pass
