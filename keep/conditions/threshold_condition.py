import chevron

from keep.conditions.base_condition import BaseCondition


class ThresholdCondition(BaseCondition):
    """Checks if a number is above or below a threshold.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, condition_type, condition_config):
        super().__init__(condition_type, condition_config)

    def apply(self, compare_to, compare_value) -> bool:
        """apply the condition.

        Args:
            compare_to (_type_): the threshold
            compare_value (_type_): the actual value

        """
        # check if compare_to is a number (supports also float, hence the . replcae)
        if str(compare_to).replace(".", "", 1).isdigit():
            compare_to = float(compare_to)
            compare_value = float(compare_value)
        # validate they are both the same type
        if type(compare_value) != type(compare_to):
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    compare_to, compare_value
                )
            )
        if self._is_percentage(compare_to) and not self._is_percentage(compare_value):
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    compare_to, compare_value
                )
            )
        return self._apply_threshold(compare_value, compare_to)

    def _is_percentage(self, a):
        if isinstance(a, int) or isinstance(a, float):
            return False

        if not a.endswith("%"):
            return False
        a = a.strip("%")
        # 0.1 is ok and 99.9 is ok
        if float(a) < 0 or float(a) > 100:
            return False
        return True

    def _apply_threshold(self, step_output, threshold):
        """Just compare the step output with the threshold.

        Args:
            step_output (_type_): _description_
            threshold (_type_): _description_

        Returns:
            _type_: _description_
        """
        if self.condition_config.get("compare_type", "gt") == "gt":
            return step_output > threshold
        elif self.condition_config.get("compare_type", "gt") == "lt":
            return step_output < threshold
        raise Exception("Invalid threshold type, currently support only gt and lt")
