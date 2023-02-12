import chevron

from keep.conditions.base_condition import BaseCondition


class ThresholdCondition(BaseCondition):
    """Checks if a number is above or below a threshold.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, condition_type, condition_config):
        super().__init__(condition_type, condition_config)

    def apply(self) -> bool:
        threshold = self.condition_config.get("value")
        compare = self.get_what_to_compare()
        if compare.isnumeric():
            compare = float(compare)
            threshold = float(threshold)
        # validate they are both the same type
        if type(threshold) != type(compare):
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    threshold, compare
                )
            )
        if self._is_percentage(threshold) and not self._is_percentage(compare):
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    threshold, compare
                )
            )
        return self._apply_threshold(compare, threshold)

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
        return step_output > threshold
