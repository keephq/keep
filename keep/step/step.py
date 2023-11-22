import asyncio
import inspect
import time
from enum import Enum

from pydantic import BaseModel

from keep.conditions.condition_factory import ConditionFactory
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.throttles.throttle_factory import ThrottleFactory


class ProviderParameter(BaseModel):
    key: str | dict | list | bool  # the key to render
    safe: bool = False  # whether to validate this key or fail silently ("safe")
    default: str | int | bool = None  # default value if this key doesn't exist


class StepType(Enum):
    STEP = "step"
    ACTION = "action"


class Step:
    def __init__(
        self,
        context_manager,
        step_id: str,
        config: dict,
        step_type: StepType,
        provider: BaseProvider,
        provider_parameters: dict,
    ):
        self.config = config
        self.step_id = step_id
        self.step_type = step_type
        self.provider = provider
        self.provider_parameters: dict[
            str, str | ProviderParameter
        ] = provider_parameters
        self.on_failure = self.config.get("provider", {}).get("on-failure", {})
        self.context_manager: ContextManager = context_manager
        self.io_handler = IOHandler(context_manager)
        self.conditions = self.config.get("condition", [])
        self.conditions_results = {}
        self.logger = context_manager.get_logger()
        self.__retry = self.on_failure.get("retry", {})
        self.__retry_count = self.__retry.get("count", 0)
        self.__retry_interval = self.__retry.get("interval", 0)

    @property
    def foreach(self):
        return self.config.get("foreach")

    @property
    def name(self):
        return self.step_id

    def run(self):
        try:
            if self.config.get("foreach"):
                did_action_run = self._run_foreach()
            else:
                did_action_run = self._run_single()
            return did_action_run
        except Exception as e:
            self.logger.error(
                "Failed to run step %s with error %s", self.step_id, e, exc_info=True
            )
            raise ActionError(e)

    def _check_throttling(self, action_name):
        throttling = self.config.get("throttle")
        # if there is no throttling, return
        if not throttling:
            return False

        throttling_type = throttling.get("type")
        throttling_config = throttling.get("with")
        throttle = ThrottleFactory.get_instance(throttling_type, throttling_config)
        alert_id = self.context_manager.get_workflow_id()
        return throttle.check_throttling(action_name, alert_id)

    def _get_foreach_items(self):
        """Get the items to iterate over, when using the `foreach` attribute (see foreach.md)"""
        # TODO: this should be part of iohandler?

        # the item holds the value we are going to iterate over
        # TODO: currently foreach will support only {{ a.b.c }} and not functions and other things (which make sense)
        index = (
            self.config.get("foreach").replace("{{", "").replace("}}", "").split(".")
        )
        index = [i.strip() for i in index]
        items = self.context_manager.get_full_context()
        for i in index:
            # try to get it as a dict
            items = items.get(i, {})
        return items

    def _run_foreach(self):
        """Evaluate the action for each item, when using the `foreach` attribute (see foreach.md)"""
        # the item holds the value we are going to iterate over
        items = self._get_foreach_items()
        any_action_run = False
        # apply ALL conditions (the decision whether to run or not is made in the end)
        for item in items:
            self.context_manager.set_for_each_context(item)
            did_action_run = self._run_single()
            # If at least one item triggered an action, return True
            # TODO - do it per item
            if did_action_run:
                any_action_run = True
        return any_action_run

    def _run_single(self):
        # Initialize all conditions
        conditions = []

        for condition in self.conditions:
            condition_name = condition.get("name", None)

            if not condition_name:
                raise Exception("Condition must have a name")

            conditions.append(
                ConditionFactory.get_condition(
                    self.context_manager,
                    condition.get("type"),
                    condition_name,
                    condition,
                )
            )

        for condition in conditions:
            condition_compare_to = condition.get_compare_to()
            condition_compare_value = condition.get_compare_value()
            try:
                condition_result = condition.apply(
                    condition_compare_to, condition_compare_value
                )
            except Exception as e:
                self.logger.error(
                    "Failed to apply condition %s with error %s",
                    condition.condition_name,
                    e,
                )
                raise
            self.context_manager.set_condition_results(
                self.step_id,
                condition.condition_name,
                condition.condition_type,
                condition_compare_to,
                condition_compare_value,
                condition_result,
                condition_alias=condition.condition_alias,
                **condition.condition_context,
            )

        # Second, decide if need to run
        # after all conditions are applied, check if we need to run
        # there are 2 cases:
        # 1. a "if" block is supplied, then use it
        # 2. no "if" block is supplied, then use the AND between all conditions
        if self.config.get("if"):
            if_conf = self.config.get("if")
        else:
            # create a string of all conditions, separated by "and"
            if_conf = " and ".join(
                [f"{{{{ {condition.condition_alias} }}}} " for condition in conditions]
            )

        # Now check it
        if if_conf:
            if_conf = self.io_handler.quote(if_conf)
            if_met = self.io_handler.render(if_conf, safe=False)
            # Evaluate the condition string
            from asteval import Interpreter

            aeval = Interpreter()
            evaluated_if_met = aeval(if_met)
            # if the evaluation failed, raise an exception
            if aeval.error_msg:
                self.logger.error(
                    f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {if_conf}, Rendered: {if_met}, Error: {aeval.error_msg}",
                    extra={
                        "condition": if_conf,
                        "rendered": if_met,
                    },
                )
                raise Exception(
                    f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {if_conf}, Rendered: {if_met}, Error: {aeval.error_msg}"
                )

        else:
            evaluated_if_met = True

        if not evaluated_if_met:
            self.logger.info(
                "Action %s evaluated NOT to run, Reason: %s evaluated to false.",
                self.config.get("name"),
                if_conf,
            )
            return

        if if_conf:
            self.logger.info(
                "Action %s evaluated to run! Reason: %s evaluated to true.",
                self.config.get("name"),
                if_conf,
            )
        else:
            self.logger.info(
                "Action %s evaluated to run! Reason: no condition, hence true.",
                self.config.get("name"),
            )

        # Third, check throttling
        # Now check if throttling is enabled
        throttled = self._check_throttling(self.config.get("name"))
        if throttled:
            self.logger.info("Action %s is throttled", self.config.get("name"))
            return

        # Last, run the action
        # if the provider is async, run it in a new event loop
        if inspect.iscoroutinefunction(self.provider.notify):
            result = self._run_single_async()
        # else, just run the provider
        else:
            try:
                rendered_providers_parameters = {}
                for parameter, value in self.provider_parameters.items():
                    if isinstance(value, ProviderParameter):
                        safe = value.safe is True and value.default is None
                        rendered_providers_parameters[
                            parameter
                        ] = self.io_handler.render(
                            value.key, safe=safe, default=value.default
                        )
                    else:
                        rendered_providers_parameters[
                            parameter
                        ] = self.io_handler.render(value, safe=True)

                for curr_retry_count in range(self.__retry_count + 1):
                    try:
                        if self.step_type == StepType.STEP:
                            step_output = self.provider.query(
                                **rendered_providers_parameters
                            )
                            self.context_manager.set_step_context(
                                self.step_id, results=step_output, foreach=self.foreach
                            )
                        else:
                            results = self.provider.notify(
                                **rendered_providers_parameters
                            )
                        # exiting the loop as step/action execution was successful
                        break
                    except Exception as e:
                        if curr_retry_count == self.__retry_count:
                            raise StepError(e)
                        else:
                            self.logger.info(
                                "Retrying running %s step after %s second(s)...",
                                self.step_id,
                                self.__retry_interval,
                            )

                            time.sleep(self.__retry_interval)

                extra_context = self.provider.expose()
                rendered_providers_parameters.update(extra_context)
                self.context_manager.set_step_provider_paremeters(
                    self.step_id, rendered_providers_parameters
                )
            except Exception as e:
                raise StepError(e)

            return True

    def _run_single_async(self):
        """For async providers, run them in a new event loop

        Raises:
            ActionError: _description_
        """
        rendered_value = self.io_handler.render_context(self.provider_parameters)
        # This is "magically solved" because of nest_asyncio but probably isn't best practice
        loop = asyncio.new_event_loop()
        if self.step_type == StepType.STEP:
            task = loop.create_task(self.provider.query(**rendered_value))
        else:
            task = loop.create_task(self.provider.notify(**rendered_value))

        for curr_retry_count in range(self.__retry_count + 1):
            try:
                loop.run_until_complete(task)

                # exiting the loop as the task execution was successful
                break
            except Exception as e:
                if curr_retry_count == self.__retry_count:
                    raise ActionError(e)
                else:
                    self.logger.info(
                        "Retrying running %s step after %s second(s)...",
                        self.step_id,
                        self.__retry_interval,
                    )

                    time.sleep(self.__retry_interval)


class StepError(Exception):
    pass
