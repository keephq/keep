import pytest

from keep.conditions.assert_condition import AssertCondition
from keep.conditions.condition_factory import ConditionFactory
from keep.conditions.stddev_condition import StddevCondition
from keep.conditions.threshold_condition import ThresholdCondition
from keep.contextmanager.contextmanager import ContextManager


def test_condition_factory():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    condition_type = "assert"
    condition_name = "mock"
    condition_config = {"assert": "mock"}
    condition = ConditionFactory.get_condition(
        context_manager, condition_type, condition_name, condition_config
    )
    assert isinstance(condition, AssertCondition)
    condition_type = "unknown"
    with pytest.raises(ModuleNotFoundError):
        condition = ConditionFactory.get_condition(
            context_manager, condition_type, condition_name, condition_config
        )


def test_assert_condition():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    assert_condtion = AssertCondition(
        context_manager=context_manager,
        condition_type="assert",
        condition_name="mock",
        condition_config={"assert": "mock"},
    )
    assertion_result = assert_condtion.apply(None, "200 == 200")
    assert assertion_result == True
    assertion_result = assert_condtion.apply(None, "200 == 201")
    assert assertion_result == False

    compare_value = assert_condtion.get_compare_value()
    assert compare_value == "mock"


def test_threshold_condition_single_threshold_gt():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "gt"},
    )
    # 200 < 100
    result = threshold_condition.apply(200, 100)
    assert result is False


def test_threshold_condition_single_threshold_lt():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "lt"},
    )
    # 200 > 100
    result = threshold_condition.apply(200, 100)
    assert result is True


def test_threshold_condition_invalid_threshold_type():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "invalid"},
    )
    with pytest.raises(Exception):
        threshold_condition.apply(200, 100)


def test_threshold_condition_invalid_threshold_value():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "gt"},
    )
    with pytest.raises(Exception, match="Invalid values for threshold") as _:
        threshold_condition.apply("200000000000x", 100)


def test_threshold_condition_different_threshold_types():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "gt"},
    )
    with pytest.raises(Exception, match="Invalid threshold value"):
        threshold_condition.apply(200000000000, "x100")


def test_threshold_condition_one_value_is_precentage():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"compare_type": "gt"},
    )
    with pytest.raises(Exception, match="Invalid threshold value"):
        threshold_condition.apply("90", "80%")


def test_threshold_condition_multithreshold():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"level": "1, 2 ,3"},
    )
    result = threshold_condition.apply("1,2,3", "4,5,6")
    assert result is True


def test_threshold_condition_multithreshold_not_equals():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    threshold_condition = ThresholdCondition(
        context_manager=context_manager,
        condition_type="threshold",
        condition_name="mock",
        condition_config={"level": "1, 2 ,3"},
    )
    with pytest.raises(
        Exception, match="Number of levels and number of thresholds do not match"
    ):
        threshold_condition.apply("1,2,3,4", "4,5,6")


def test_stddev_condition():
    context_manager = ContextManager(tenant_id="mock", workflow_id=None)
    stddev_condition = StddevCondition(
        context_manager=context_manager,
        condition_type="stddev",
        condition_name="mock",
        condition_config={},
    )
    result = stddev_condition.apply(1, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert result is True
