from keep.providers.base.base_provider import BaseProvider


class Step:
    def __init__(self, step_id, step_config, provider: BaseProvider):
        self.step_id = step_id
        self.step_config = step_config
        self.step_conditions = step_config.get("condition", [])
        self.provider = provider

    def run(self, context):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Run the step query
            step_output = self.provider.query(context)
            # Validate the step output
            self._post_step_validations(step_output, context)
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        pass

    def _post_step_validations(self, context, step_output):
        for condition in self.step_conditions:
            condition = Condition(**condition)
            condition.apply(context, step_output)


class StepError(Exception):
    pass
