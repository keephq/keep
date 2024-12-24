import time
from unittest.mock import Mock

import pytest

from keep.step.step import Step, StepError, StepType

# constants for on-failure->retry mechanism
RETRY_COUNT = 2
RETRY_INTERVAL = 1


@pytest.fixture
def sample_step():
    context_manager = Mock()
    step_id = "test_step"
    config = {
        "name": "Test Step",
        "provider": {
            "on-failure": {"retry": {"count": RETRY_COUNT, "interval": RETRY_INTERVAL}}
        },
        "throttle": False,
    }
    step_type = StepType.STEP
    provider = Mock()
    provider.expose = Mock(return_value={})
    provider_parameters = {"param1": "value1", "param2": "value2"}

    step = Step(
        context_manager,
        step_id,
        config,
        step_type,
        provider,
        provider_parameters,
    )

    # Mock the context
    step.io_handler.render_context = Mock(
        return_value={"param1": "value1", "param2": "value2"}
    )

    return step

@pytest.mark.asyncio
async def test_run_single(sample_step):
    # Simulate the result
    sample_step.provider.query = Mock(return_value="result")

    # Run the method
    result = await sample_step._run_single()

    # Assertions
    assert result is True  # Action should run successfully
    sample_step.provider.query.assert_called_with(param1="value1", param2="value2")
    assert sample_step.provider.query.call_count == 1

@pytest.mark.asyncio
async def test_run_single_exception(sample_step):
    # Simulate an exception
    sample_step.provider.query = Mock(side_effect=Exception("Test exception"))

    start_time = time.time()

    # Run the method and expect an exception to be raised
    with pytest.raises(StepError):
        await sample_step._run_single()

    end_time = time.time()
    execution_time = end_time - start_time

    # Provider query should be called RETRY_COUNT+1 times
    assert sample_step.provider.query.call_count == RETRY_COUNT + 1

    # _run_single should take around RETRY_COUNT*RETRT_INTERVAL time due to retries
    assert execution_time >= RETRY_COUNT * RETRY_INTERVAL
