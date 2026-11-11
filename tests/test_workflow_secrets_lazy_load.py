"""
Workflow secrets must be loaded when a workflow runs, not when it is built.

WorkflowManager.insert_events() builds a Workflow object for every workflow on
every event batch, including workflows whose triggers do not match. Loading the
secrets in Workflow.__init__ meant one secret manager read per workflow per
event batch.
"""

from unittest.mock import MagicMock

from keep.workflowmanager.workflow import Workflow


def _workflow(context_manager, disabled=False):
    return Workflow(
        context_manager=context_manager,
        workflow_id="test-workflow",
        workflow_revision=1,
        workflow_name="test-workflow",
        workflow_owners=[],
        workflow_tags=[],
        workflow_interval=0,
        workflow_triggers=[],
        workflow_steps=[],
        workflow_actions=[],
        workflow_disabled=disabled,
    )


def test_secrets_not_loaded_when_workflow_is_built():
    context_manager = MagicMock()
    _workflow(context_manager)
    context_manager.set_secret_context.assert_not_called()


def test_secrets_loaded_once_when_workflow_runs():
    context_manager = MagicMock()
    workflow = _workflow(context_manager)
    workflow.run("execution-id")
    context_manager.set_secret_context.assert_called_once_with()


def test_secrets_not_loaded_for_disabled_workflow():
    context_manager = MagicMock()
    workflow = _workflow(context_manager, disabled=True)
    workflow.run("execution-id")
    context_manager.set_secret_context.assert_not_called()
