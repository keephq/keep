import asyncio
import inspect
import logging

from pydantic.dataclasses import dataclass

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.statemanager.statemanager import StateManager
from keep.throttles.throttle_factory import ThrottleFactory


@dataclass(config={"arbitrary_types_allowed": True})
class Action:
    name: str
    config: dict
    provider: BaseProvider
    provider_context: dict

    def __post_init__(self):
        self.logger = logging.getLogger(__name__)
        self.io_handler = IOHandler()
        self.context_manager = ContextManager.get_instance()
        self.state_manager = StateManager.get_instance()

    def run(self):
        # Check if needs to run
        need_to_run = self._check_conditions()
        if not need_to_run:
            self.logger.info("Action %s evaluated NOT to run", self.config.get("name"))
            return
        throttled = self._check_throttling(self.config.get("name"))
        if throttled:
            self.logger.info("Action %s is throttled", self.config.get("name"))
            return
        try:
            if self.config.get("foreach"):
                self._run_foreach()
            else:
                self._run_single()
            return True
        except Exception as e:
            raise ActionError(e)

    def _check_conditions(self):
        self.logger.debug("Checking conditions for action %s", self.config.get("name"))
        full_context = self.context_manager.get_full_context()
        conditions_eval = self.config.get("if", [])
        # default behaviour should be ALL conditions should be met
        if not conditions_eval:
            for step in full_context.get("steps"):
                # TODO - wrap it else
                if step == "this":
                    continue
                for condition, condition_results in (
                    full_context.get("steps").get(step).get("conditions").items()
                ):
                    # One of the conditions has been met
                    if any([c["result"] for c in condition_results]):
                        return True

        # if there's a condition, evaluate it
        else:
            condition_met = self.io_handler.render(conditions_eval)
            condition_met = eval(condition_met)
            if condition_met:
                return True
            else:
                return False

    def _check_throttling(self, action_name):
        throttling = self.config.get("throttle")
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
            self.context_manager.set_for_each_context(val)
            rendered_value = self.io_handler.render_context(self.provider_context)
            self.provider.notify(**rendered_value)

    def _run_single(self):
        rendered_value = self.io_handler.render_context(self.provider_context)
        # if the provider is async, run it in a new event loop
        if inspect.iscoroutinefunction(self.provider.notify):
            result = self._run_single_async()
        # else, just run the provider
        else:
            self.provider.notify(**rendered_value)

    def _run_single_async(self):
        """For async providers, run them in a new event loop

        Raises:
            ActionError: _description_
        """
        rendered_value = self.io_handler.render_context(self.provider_context)
        # This is "magically solved" because of nest_asyncio but probably isn't best practice
        loop = asyncio.new_event_loop()
        task = loop.create_task(self.provider.notify(**rendered_value))
        try:
            loop.run_until_complete(task)
        except Exception as e:
            raise ActionError(e)
