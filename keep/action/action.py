import asyncio
import inspect
import logging
import re

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.statemanager.statemanager import StateManager
from keep.throttles.throttle_factory import ThrottleFactory


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
        self.state_manager = StateManager.get_instance()

    def run(self):
        throttled = self._check_throttling(self.action_config.get("name"))
        if throttled:
            self.logger.debug("Action %s is throttled", self.action_config.get("name"))
            return
        try:
            if self.action_config.get("foreach"):
                self._run_foreach()
            else:
                self._run_single()
        except Exception as e:
            raise ActionError(e)

    def _check_throttling(self, action_name):
        throttling = self.action_config.get("throttle")
        # if there is no throttling, return
        if not throttling:
            return False

        throttling_type = throttling.get("type")
        throttling_config = throttling.get("with")
        throttle = ThrottleFactory.get_instance(throttling_type, throttling_config)
        alert_id = self.context_manager.get_alert_id()
        return throttle.check_throttling(action_name, alert_id)

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
        if inspect.iscoroutinefunction(self.provider.notify):
            asyncio.run(self.provider.notify(**rendered_value))
        else:
            self.provider.notify(**rendered_value)
