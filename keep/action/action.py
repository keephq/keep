import logging
import re

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


class Action:
    def __init__(
        self, name: str, config, provider: BaseProvider, provider_context: dict
    ):
        self.name = name
        self.logger = logging.getLogger(__name__)
        self.provider = provider
        self.provider_context = provider_context
        self.action_config = config
        self.io_handler = IOHandler()
        self.context_manager = ContextManager.get_instance()

    def run(self):
        try:
            if self.action_config.get("foreach"):
                self._run_foreach()
            else:
                self._run_single()
        except Exception as e:
            raise ActionError(e)

    def _run_foreach(self):
        foreach_iterator = self.context_manager.get_actionable_results()
        for val in foreach_iterator:
            self.context_manager.set_for_each_context(
                val.get("condition").get("raw_value")
            )
            rendered_value = self.io_handler.render_context(self.provider_context)
            self.provider.notify(**rendered_value)

    def _run_single(self):
        rendered_value = self.io_handler.render_context(self.provider_context)
        self.provider.notify(**rendered_value)
