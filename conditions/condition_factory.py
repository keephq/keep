import importlib

from keep.conditions.base_condition import BaseCondition
from keep.contextmanager.contextmanager import ContextManager


class ConditionFactory:
    @staticmethod
    def get_condition(
        context_manager: ContextManager,
        condition_type,
        condition_name,
        condition_config,
    ) -> BaseCondition:
        module = importlib.import_module(f"keep.conditions.{condition_type}_condition")
        condition_class = getattr(
            module, condition_type.title().replace("_", "") + "Condition"
        )
        return condition_class(
            context_manager, condition_type, condition_name, condition_config
        )
