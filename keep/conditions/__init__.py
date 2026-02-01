class Condition:
    def __init__(self, condition_type, condition_config):
        self.condition_type = condition_type
        self.condition_config = condition_config

    def apply(self, context, step_output):
        pass
