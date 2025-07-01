import pytest
import asyncio
import time

from keep.api.core.db import get_last_workflow_execution_by_workflow_id
from keep.workflowmanager.workflowscheduler import WorkflowScheduler
from keep.workflowmanager.workflowmanager import WorkflowManager


@pytest.fixture
def workflow_manager():
    """
    Fixture to create and manage a WorkflowManager instance.
    IMPORTANT: Do not use together with test_app fixture or scheduler instance won't be updated.
    """
    manager = None
    try:

        scheduler = WorkflowScheduler(None)
        manager = WorkflowManager.get_instance()
        scheduler.workflow_manager = manager
        manager.scheduler = scheduler
        asyncio.run(manager.start())
        yield manager
    except Exception:
        pass
    if manager:
        try:
            manager.stop()
            # Give some time for threads to clean up
            time.sleep(1)
        except Exception as e:
            print(f"Error stopping workflow manager: {e}")


def wait_for_workflow_execution(
    tenant_id, workflow_id, max_wait_count=30, exclude_ids=None
):
    # Wait for the workflow execution to complete
    workflow_execution = None
    count = 0
    while (
        workflow_execution is None or workflow_execution.status == "in_progress"
    ) and count < max_wait_count:
        try:
            workflow_execution = get_last_workflow_execution_by_workflow_id(
                tenant_id, workflow_id, exclude_ids=exclude_ids
            )
        except Exception as e:
            print(
                f"DEBUG: Poll attempt {count}: execution_id={workflow_execution.id if workflow_execution else None}, "
                f"status={workflow_execution.status if workflow_execution else None}, "
                f"error={e}"
            )
        finally:
            time.sleep(1)
            count += 1
    return workflow_execution
