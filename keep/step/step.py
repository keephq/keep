import exception

from keep.providers import Provider


class Step:
    def __init__(self, name, provider: Provider):
        self.name = name
        self.provider = provider

    def run(self, context):
        try:
            step_output = self.provider.run(context)
        except Exception as e:
            raise StepError(e)

        return step_output


class StepError(Exception):
    pass
