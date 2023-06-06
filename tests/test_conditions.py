import pytest

from keep.conditions.assert_condition import AssertCondition
from keep.conditions.condition_factory import ConditionFactory


def test_condition_factory():
    condition_type = "assert"
    condition_name = "mock"
    condition_config = {"assert": "mock"}
    condition = ConditionFactory.get_condition(
        condition_type, condition_name, condition_config
    )
    assert isinstance(condition, AssertCondition)
    condition_type = "unknown"
    with pytest.raises(ModuleNotFoundError):
        condition = ConditionFactory.get_condition(
            condition_type, condition_name, condition_config
        )


def test_assert_condition():
    assert_condtion = AssertCondition(
        condition_type="assert",
        condition_name="mock",
        condition_config={"assert": "mock"},
    )
    assertion_result = assert_condtion.apply(None, "200 == 200")
    assert assertion_result == False
    assertion_result = assert_condtion.apply(None, "200 == 201")
    assert assertion_result == True

    compare_value = assert_condtion.get_compare_value()
    assert compare_value == "mock"


def test_threshold_condition():
    assert True
