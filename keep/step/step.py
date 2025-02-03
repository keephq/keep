import logging
import time
from enum import Enum

from keep.conditions.condition_factory import ConditionFactory
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.step.step_provider_parameter import StepProviderParameter
from keep.throttles.throttle_factory import ThrottleFactory


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
        self.provider_parameters: dict[str, str | StepProviderParameter] = (
            provider_parameters
        )
        self.on_failure = self.config.get("provider", {}).get("on-failure", {})
        self.context_manager: ContextManager = context_manager
        self.io_handler = IOHandler(context_manager)
        self.conditions = self.config.get("condition", [])
        self.vars = self.config.get("vars", {})
        self.conditions_results = {}
        self.logger = logging.getLogger(__name__)
        self.__retry = self.on_failure.get("retry", {})
        self.__retry_count = self.__retry.get("count", 0)
        self.__retry_interval = self.__retry.get("interval", 0)
        self.__continue_to_next_step = self.config.get("continue", True)

    @property
    def foreach(self):
        return self.config.get("foreach")

    @property
    def name(self):
        return self.step_id

    @property
    def continue_to_next_step(self):
        return self.__continue_to_next_step

    def _dont_render(self):
        # special case for Keep provider on _notify with "if" - it should render the parameters itself
        return self.step_type == StepType.ACTION and "KeepProvider" in str(
            self.provider.__class__
        )

    def run(self):
        try:
            if self.config.get("foreach"):
                did_action_run = self._run_foreach()
            # special case for Keep provider on _notify with "if" - it should render the parameters itself
            elif self._dont_render():
                did_action_run = self._run_single(dont_render=True)
            else:
                did_action_run = self._run_single()
            return did_action_run
        except Exception as e:
            self.logger.warning(
                "Failed to run step %s with error %s",
                self.step_id,
                e,
                extra={
                    "step_id": self.step_id,
                },
                exc_info=True,
            )
            raise ActionError(e)

    def _check_throttling(self, action_name):
        throttling = self.config.get("throttle")
        # if there is no throttling, return
        if not throttling:
            return False

        throttling_type = throttling.get("type")
        throttling_config = throttling.get("with")
        throttle = ThrottleFactory.get_instance(
            self.context_manager, throttling_type, throttling_config
        )
        workflow_id = self.context_manager.get_workflow_id()
        event_id = self.context_manager.event_context.event_id
        return throttle.check_throttling(action_name, workflow_id, event_id)

    def _get_foreach_items(self) -> list | list[list]:
        """Get the items to iterate over, when using the `foreach` attribute (see foreach.md)"""
        # TODO: this should be part of iohandler?

        # the item holds the value we are going to iterate over
        # TODO: currently foreach will support only {{ a.b.c }} and not functions and other things (which make sense)
        foreach_split = self.config.get("foreach").split("&&")
        foreach_items = []
        for foreach in foreach_split:
            index = foreach.replace("{{", "").replace("}}", "").split(".")
            index = [i.strip() for i in index]
            items = self.context_manager.get_full_context()
            for i in index:
                if isinstance(items, dict):
                    items = items.get(i, {})
                else:
                    items = getattr(items, i, {})
            foreach_items.append(items)
        if not foreach_items:
            return []
        return len(foreach_items) == 1 and foreach_items[0] or zip(*foreach_items)

    def _run_foreach(self):
        """Evaluate the action for each item, when using the `foreach` attribute (see foreach.md)"""
        # the item holds the value we are going to iterate over
        items = self._get_foreach_items()
        any_action_run = False
        # apply ALL conditions (the decision whether to run or not is made in the end)
        for item in items:
            self.context_manager.set_for_each_context(item)
            try:
                did_action_run = self._run_single()
            except Exception as e:
                self.logger.warning(
                    "Failed to run step %s with error %s",
                    self.step_id,
                    e,
                    extra={
                        "step_id": self.step_id,
                    },
                    exc_info=True,
                )
                continue
            # If at least one item triggered an action, return True
            # TODO - do it per item
            if did_action_run:
                any_action_run = True
        return any_action_run

    def _run_single(self, dont_render=False):
        # Initialize all conditions
        conditions = []

        aliases = self.config.get("alias", {})

        # if aliases are defined, set them in the context
        for alias_key, alias_val in aliases.items():
            aliases[alias_key] = self.io_handler.render(alias_val)

        self.context_manager.set_step_vars(
            self.step_id, _vars=self.vars, _aliases=aliases
        )

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
                    extra={
                        "step_id": self.step_id,
                    },
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
            quoted_if_conf = self.io_handler.quote(if_conf)
            if_met = self.io_handler.render(quoted_if_conf, safe=False)
            # Evaluate the condition string
            from asteval import Interpreter

            aeval = Interpreter()
            evaluated_if_met = aeval(if_met)
            # tb: when Shahar and I debugged, conclusion was:
            if isinstance(evaluated_if_met, str):
                evaluated_if_met = aeval(evaluated_if_met)
            # if the evaluation failed, raise an exception
            if aeval.error_msg and if_conf == quoted_if_conf:
                self.logger.error(
                    f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {quoted_if_conf}, Rendered: {if_met}, Error: {aeval.error_msg}",
                    extra={
                        "condition": quoted_if_conf,
                        "rendered": if_met,
                        "step_id": self.step_id,
                    },
                )
                raise Exception(
                    f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {if_conf}, Rendered: {if_met}, Error: {aeval.error_msg}"
                )
            # maybe its because of quoting, try again without quoting
            elif aeval.error_msg:
                # without quoting
                aeval_without_quote = Interpreter()
                if_met = self.io_handler.render(if_conf, safe=False)
                evaluated_if_met = aeval_without_quote(if_met)
                if isinstance(evaluated_if_met, str):
                    evaluated_if_met = aeval_without_quote(evaluated_if_met)
                # if again error, raise an exception
                if aeval_without_quote.error_msg:
                    raise Exception(
                        f"Failed to evaluate if condition, you probably used a variable that doesn't exist. Condition: {if_conf}, Rendered: {if_met}, Error: {aeval_without_quote.error_msg}"
                    )

        else:
            evaluated_if_met = True

        action_name = self.config.get("name")
        if not evaluated_if_met:
            self.logger.info(
                f"Action {action_name} evaluated NOT to run, Reason: {if_met} evaluated to false. [before evaluation: {if_conf}]",
                extra={
                    "condition": if_conf,
                    "rendered": if_met,
                    "step_id": self.step_id,
                },
            )
            return

        if if_conf:
            self.logger.info(
                f"Action {action_name} evaluated to run! Reason: {if_met} evaluated to true.",
                extra={
                    "condition": if_conf,
                    "rendered": if_met,
                    "step_id": self.step_id,
                },
            )
        else:
            self.logger.info(
                "Action %s evaluated to run! Reason: no condition, hence true.",
                self.config.get("name"),
                extra={
                    "step_id": self.step_id,
                },
            )

        # Third, check throttling
        # Now check if throttling is enabled
        self.logger.info(
            "Checking throttling for action %s",
            self.config.get("name"),
            extra={
                "step_id": self.step_id,
            },
        )
        throttled = self._check_throttling(self.config.get("name"))
        if throttled:
            self.logger.info(
                "Action %s is throttled",
                self.config.get("name"),
                extra={
                    "step_id": self.step_id,
                },
            )
            return
        self.logger.info(
            "Action %s is not throttled",
            self.config.get("name"),
            extra={
                "step_id": self.step_id,
            },
        )

        # Last, run the action
        try:
            if not dont_render:
                rendered_providers_parameters = self.io_handler.render_context(
                    self.provider_parameters
                )
            # special case for Keep provider (alert evaluation engine)
            # which needs to evaluate the provider parameters by itself
            else:
                rendered_providers_parameters = self.provider_parameters

            for curr_retry_count in range(self.__retry_count + 1):
                self.logger.info(
                    f"Running {self.step_id} {self.step_type}, current retry: {curr_retry_count}",
                    extra={
                        "step_id": self.step_id,
                    },
                )
                try:
                    if self.step_type == StepType.STEP:
                        step_output = self.provider.query(
                            **rendered_providers_parameters
                        )
                    else:
                        step_output = self.provider.notify(
                            **rendered_providers_parameters
                        )
                    # exiting the loop as step/action execution was successful
                    self.context_manager.set_step_context(
                        self.step_id, results=step_output, foreach=self.foreach
                    )
                    break
                except Exception as e:
                    if curr_retry_count == self.__retry_count:
                        raise StepError(e)
                    else:
                        self.logger.info(
                            "Retrying running %s step after %s second(s)...",
                            self.step_id,
                            self.__retry_interval,
                            extra={
                                "step_id": self.step_id,
                            },
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


class StepError(Exception):
    pass
