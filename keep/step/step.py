import logging
from dataclasses import field

import chevron
from pydantic.dataclasses import dataclass

from keep.conditions.condition_factory import ConditionFactory
from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


@dataclass(config={"arbitrary_types_allowed": True})
class Step:
    step_id: str
    step_config: dict
    provider: BaseProvider
    provider_parameters: dict
    step_conditions_results: dict = field(default_factory=dict)
    step_conditions: list = field(default_factory=list)

    def __post_init__(self):
        self.step_conditions = self.step_config.get("condition", [])
        self.io_handler = IOHandler()
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager.get_instance()

    def run(self):
        try:
            # Check if the step needs to run
            self._pre_step_validations()
            # Inject the context to the parameters
            for parameter in self.provider_parameters:
                self.provider_parameters[parameter] = self._inject_context_to_parameter(
                    self.provider_parameters[parameter]
                )
            step_output = self.provider.query(**self.provider_parameters)
            self.context_manager.set_step_context(self.step_id, results=step_output)
            # Validate the step output
            self._post_step_validations()
        except Exception as e:
            raise StepError(e)

        return step_output

    def _pre_step_validations(self):
        self.logger.debug("Pre step validation")
        self.logger.debug("Pre Step validation success")

    def _post_step_validations(self):
        self.logger.debug("Post step validation")
        foreach = self.step_config.get("foreach")
        if foreach:
            self._post_each_step_validations(foreach.get("value"))
        else:
            self._post_single_step_validations()
        self.logger.debug("Post Step validation success")

    def _post_each_step_validations(self, foreach_value_template):
        context = self.context_manager.get_full_context()
        foreach_actual_value = self._get_actual_value(foreach_value_template)
        for value in foreach_actual_value:
            # will be use inside the io handler
            self.context_manager.set_for_each_context(value)
            for condition in self.step_conditions:
                condition_type = condition.get("type")
                condition_alias = condition.get("alias")
                condition = ConditionFactory.get_condition(condition_type, condition)
                condition_what_to_compare = condition.get_compare_to()
                condition_compare_value = condition.get_compare_value()
                condition_result = condition.apply(
                    condition_what_to_compare, condition_compare_value
                )
                self.context_manager.set_condition_results(
                    self.step_id,
                    condition_type,
                    condition_compare_value,
                    condition_what_to_compare,
                    condition_result,
                    condition_alias=condition_alias,
                    raw_value=value,
                )

    def _post_single_step_validations(self):
        for condition in self.step_conditions:
            condition_type = condition.get("type")
            condition_alias = condition.get("alias")
            condition = ConditionFactory.get_condition(condition_type, condition)
            condition_compare_to = condition.get_compare_to()
            condition_compare_value = condition.get_compare_value()
            condition_result = condition.apply(
                condition_compare_to, condition_compare_value
            )
            self.context_manager.set_condition_results(
                self.step_id,
                condition_type,
                condition_compare_to,
                condition_compare_value,
                condition_result,
                condition_alias=condition_alias,
            )
        self.logger.debug("Post Step validation success")

    def _get_actual_value(self, foreach_value_template):
        val = self.io_handler.render(foreach_value_template)
        return val

    def _inject_context_to_parameter(self, template):
        context = self.context_manager.get_full_context()
        return chevron.render(template, context)

    @property
    def failure_strategy(self):
        return self.step_config.get("failure_strategy")


class StepError(Exception):
    pass
