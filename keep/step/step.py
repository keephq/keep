from keep.providers import Provider


class Step:
    def __init__(self, step_id, step_config, provider: Provider):
        self.step_id = step_id
        self.step_config = step_config
        self.provider = provider

    def run(self, context):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Run the step query
            step_output = self.provider.query(context, self.step_config)
            # Validate the step output
            self._post_step_validations(step_output)
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        pass

    def _post_step_validations(self, step_output):
        pass


class StepError(Exception):
    pass
