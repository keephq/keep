import chevron

from keep.conditions.base_condition import BaseCondition


class ThresholdCondition(BaseCondition):
    """Checks if a number is above or below a threshold.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, condition_type, condition_config):
        super().__init__(condition_type, condition_config)

    def apply(self, context) -> bool:
        threshold = self.condition_config.get("value")
        step_output = context.get("steps").get("this").get("results")
        compare = self._get_what_to_compare(context)
        # validate they are both the same type
        if type(threshold) != type(compare):
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    threshold, step_output
                )
            )
        return self._apply_threshold(compare, threshold)

    def _is_percentage(self, a):
        if isinstance(a, int):
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

    def _get_what_to_compare(self, context):
        """Get the value to compare.

        Args:
            step_output (_type_): _description_

        Returns:
            _type_: _description_
        """
        compare_to = self.condition_config.get("compare_to")
        # if the compare to is not available, just return the step output
        if not compare_to:
            return step_output

        compare_to = self.io_handler.render(compare_to, context)
        return compare_to
