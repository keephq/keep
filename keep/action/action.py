import chevron

from keep.iohandler.iohandler import IOHandler


class Action:
    def __init__(self, name, context, provider, provider_action_config):
        self.name = name
        # List of context to be added to the output template
        self.output_context_list = context
        self.provider = provider
        self.provider_action_config = provider_action_config
        self.io_handler = IOHandler()

    def run(self, alert_context):
        try:
            context = {}
            for output_context in self.output_context_list:
                context[output_context.get("name")] = self._inject_context(
                    output_context.get("value"), alert_context
                )

            template = self.provider.get_template()
            alert_message = self._inject_context(template, context)
            self.provider.notify(alert_message)
        except Exception as e:
            raise ActionError(e)

    def _inject_context(self, template, context):
        return chevron.render(template, context)
