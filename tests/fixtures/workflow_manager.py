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


def _get_workflow_ids_in_run_queue(workflow_manager: WorkflowManager):
    """Helper function to extract workflow IDs from the run queue."""
    if (
        not workflow_manager.scheduler
        or not workflow_manager.scheduler.workflows_to_run
    ):
        return []
    return [
        workflow.get("workflow_id")
        for workflow in workflow_manager.scheduler.workflows_to_run
    ]


def wait_for_workflow_in_run_queue(workflow_id, max_wait_count=30):
    """
    Wait for the workflow to be in the run queue.

    Args:
        workflow_id: The ID of the workflow to wait for
        max_wait_count: Maximum number of seconds to wait (default: 30)

    Returns:
        bool: True if workflow is found in run queue, False if timeout reached
    """
    workflow_manager = WorkflowManager.get_instance()

    for _ in range(max_wait_count):
        workflow_ids_in_queue = _get_workflow_ids_in_run_queue(workflow_manager)

        if workflow_id in workflow_ids_in_queue:
            return True

        time.sleep(1)

    # Final check after timeout
    workflow_ids_in_queue = _get_workflow_ids_in_run_queue(workflow_manager)
    return workflow_id in workflow_ids_in_queue
