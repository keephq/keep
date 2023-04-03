import chevron

from keep.conditions.base_condition import BaseCondition


class AssertCondition(BaseCondition):
    """Use python assert to check if a condition is true.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, *kargs, **kwargs):
        super().__init__(*kargs, **kwargs)

    def apply(self, compare_to, compare_value) -> bool:
        """apply the condition.

        Args:
            compare_to (_type_): the threshold
            compare_value (_type_): the actual value

        """
        try:
            self.logger.debug(f"Asserting {compare_value}")
            assert eval(compare_value)
            self.logger.debug(f"Asserted {compare_value}")
            return False
        # if the assertion failed, an action should be done
        except AssertionError:
            self.logger.debug(f"Failed asserting {compare_value}")
            return True

    def get_compare_value(self):
        """Get the value to compare. The actual value from the step output.

        Args:
            step_output (_type_): _description_

        Returns:
            _type_: _description_
        """
        compare_value = self.condition_config.get("assert")
        compare_value = self.io_handler.render(compare_value)
        return compare_value
