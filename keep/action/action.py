class Action:
    def __init__(self, name, context, provider, provider_action_config):
        self.name = name
        self.context = context
        self.provider = provider
        self.provider_action_config = provider_action_config

    def run(self, context):
        try:
            self.provider.notify(alert_message)
        except Exception as e:
            raise ActionError(e)
