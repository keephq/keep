import statistics

from keep.conditions.base_condition import BaseCondition


class StddevCondition(BaseCondition):
    """Apply sttdev to the input."""

    def __init__(self, *kargs, **kwargs):
        super().__init__(*kargs, **kwargs)
        self.pivot_column = None
        self.condition_context["stddev"] = []

    def _filter_values_by_stddev(self, lst, threshold):
        # use only the pivot column
        if self.pivot_column:
            _lst = [c[self.pivot_column] for c in lst]
        else:
            _lst = lst

        mean = statistics.mean(_lst)
        stddev = statistics.stdev(_lst, mean)

        results = []
        for i, x in enumerate(_lst):
            x_stddev = abs(x - mean) / stddev
            self.condition_context["stddev"].append(
                {"value": lst[i], "stddev": x_stddev, "mean": mean}
            )
            if x_stddev > threshold:
                results.append(i)
        return results

    def apply(self, compare_to, compare_value) -> bool:
        """apply the condition.

        Args:
            compare_to (float): the stddev threshold
            compare_value (list): the list of values (numbers/floats)

        """
        values = self._filter_values_by_stddev(compare_value, compare_to)
        # If there are any values that are outside the standard devitation
        if values:
            return True
        return False

    def get_compare_value(self):
        """Get the value to compare. The actual value from the step output.

        Args:
            step_output (_type_): _description_

        Returns:
            _type_: _description_
        """
        compare_value = self.condition_config.get("value")
        rendered_compare_value = self.io_handler.render(compare_value)
        self.pivot_column = self.condition_config.get("pivot_column", 0)
        return rendered_compare_value
