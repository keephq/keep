from keep.conditions.base_condition import BaseCondition


class ThresholdCondition(BaseCondition):
    """Checks if a number is above or below a threshold.

    Args:
        BaseCondition (_type_): _description_
    """

    def __init__(self, *kargs, **kwargs):
        super().__init__(*kargs, **kwargs)
        self.levels = []

    def _check_if_multithreshold(self, compare_to):
        """Checks if this is a multithreshold condition.

        Args:
            compare_to (str): for single threshold could be 60 or 60%, for multithreshold
                              will be 60, 70, 80 (comma separated values)

        Raises:
            ValueError: If the number of levels and number of thresholds do not match

        Returns:
            bool: True if multithreshold, False otherwise
        """
        # TODO make more validations
        if "," in str(compare_to):
            levels = self.condition_config.get("level")
            if len(levels.split(",")) != len(compare_to.split(",")):
                raise ValueError(
                    "Number of levels and number of thresholds do not match"
                )
            self.levels = [level.strip() for level in levels.split(",")]
            return True
        return False

    def _apply_multithreshold(self, compare_to, compare_value):
        """Applies threshold for more than one threshold value (aka "multithreshold")

        Args:
            compare_to (list[str]): comma seperated list (e.g. 60, 70, 80)
            compare_value (list[str]: comma seperated list (e.g. major, medium, minor)

        Returns:
            bool: true if threshold applies, false otherwise
        """
        thresholds = [t.strip() for t in compare_to.split(",")]
        for i, threshold in enumerate(thresholds):
            if self._apply_threshold(compare_value, threshold):
                # Keep the level in the condition context
                self.condition_context["level"] = self.levels[i]
                return True
        return False

    def _validate(self, compare_to, compare_value):
        """validate the condition.

        Args:
            compare_to (_type_): the threshold
            compare_value (_type_): the actual value

        """
        # check if compare_to is a number (supports also float, hence the . replace)
        if (
            str(compare_to).replace(".", "", 1).isdigit()
            and str(compare_to).replace(".", "", 1).isdigit()
        ):
            compare_to = float(compare_to)
            try:
                compare_value = float(compare_value)
            except ValueError as exc:
                raise Exception(
                    "Invalid values for threshold - the compare_to is a float where the compare_value is not"
                ) from exc
        # validate they are both the same type
        if not isinstance(compare_value, type(compare_to)):
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
        return compare_to, compare_value

    def apply(self, compare_to, compare_value) -> bool:
        """apply the condition.

        Args:
            compare_to (_type_): the threshold
            compare_value (_type_): the actual value

        """
        if self._check_if_multithreshold(compare_to):
            return self._apply_multithreshold(compare_to, compare_value)

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
        step_output, threshold = self._validate(step_output, threshold)
        if self.condition_config.get("compare_type", "gt") == "gt":
            return step_output > threshold
        elif self.condition_config.get("compare_type", "gt") == "lt":
            return step_output < threshold
        raise Exception("Invalid threshold type, currently support only gt and lt")
