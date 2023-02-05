from keep.conditions.base_condition import BaseCondition


class ThresholdCondition(BaseCondition):
    """Checks if a number is above or below a threshold.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, condition_type, condition_config):
        super().__init__(condition_type, condition_config)

    def apply(self, context, step_output) -> bool:
        threshold = self.condition_config.get("value")
        # validate they are both numeric or percentage
        if self._is_percentage(threshold) and self._is_percentage(step_output):
            return self._apply_threshold(step_output, threshold)
        elif threshold.isnumeric() and step_output.isnumeric():
            return self._apply_threshold(step_output, threshold)
        else:
            raise Exception(
                "Invalid threshold value, currently support only numeric and percentage values but got {} and {}".format(
                    threshold, step_output
                )
            )

    def _is_percentage(self, a):
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
