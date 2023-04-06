import importlib

from keep.conditions.base_condition import BaseCondition


class ConditionFactory:
    @staticmethod
    def get_condition(
        condition_type, condition_name, condition_config
    ) -> BaseCondition:
        module = importlib.import_module(f"keep.conditions.{condition_type}_condition")
        condition_class = getattr(
            module, condition_type.title().replace("_", "") + "Condition"
        )
        return condition_class(condition_type, condition_name, condition_config)
