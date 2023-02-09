import chevron

from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


class Action:
    def __init__(self, name: str, provider: BaseProvider, provider_context: dict):
        self.name = name
        self.provider = provider
        self.provider_context = provider_context
        self.io_handler = IOHandler()

    def run(self, alert_context):
        try:
            self._render_context(self.provider_context, alert_context)
            self.provider.notify(**self.provider_context)
        except Exception as e:
            raise ActionError(e)

    def _render_context(self, context_to_render: dict, alert_context: dict):
        """
        Iterates the provider context and renders it using the alert context.
        """
        for key, value in context_to_render.items():
            if isinstance(value, str):
                context_to_render[key] = self._render_template_with_context(
                    value, alert_context
                )
            elif isinstance(value, list):
                self._render_list_context(value, alert_context)
            elif isinstance(value, dict):
                self._render_context(value, alert_context)

    def _render_list_context(self, context_to_render: list, alert_context: dict):
        """
        Iterates the provider context and renders it using the alert context.
        """
        for i in range(0, len(context_to_render)):
            value = context_to_render[i]
            if isinstance(value, str):
                context_to_render[i] = self._render_template_with_context(
                    value, alert_context
                )
            if isinstance(value, list):
                self._render_list_context(value, alert_context)
            if isinstance(value, dict):
                self._render_context(value, alert_context)

    def _render_template_with_context(self, template: str, alert_context: dict) -> str:
        """
        Renders a template with the given context.

        Args:
            template (str): template (string) to render
            alert_context (dict): alert run context

        Returns:
            str: rendered template
        """
        return chevron.render(template, alert_context)
