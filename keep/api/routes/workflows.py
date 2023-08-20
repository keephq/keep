import logging
from dataclasses import asdict
from functools import reduce
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.workflow import WorkflowDTO
from keep.contextmanager.contextmanager import ContextManager
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.workflowmanager.workflowstore import WorkflowStore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get workflows",
)
def get_workflows(
    tenant_id: str = Depends(verify_bearer_token),
) -> list[WorkflowDTO]:
    workflowstore = WorkflowStore()
    workflows = workflowstore.get_all_workflows(tenant_id=tenant_id)
    workflows_dto = [
        WorkflowDTO(
            id=workflow.workflow_id,
            description=workflow.workflow_description,
            owners=workflow.workflow_owners,
            interval=workflow.workflow_interval,
            steps=[asdict(step) for step in workflow.workflow_steps],
            actions=[asdict(action) for action in workflow.workflow_actions],
        )
        for workflow in workflows
    ]
    return workflows_dto


@router.post(
    "/run/{aworkflow_id}",
    description="Run a workflow",
)
def run_workflow(
    workflow_id: str,
    body: Optional[Dict[Any, Any]] = Body(None),
    tenant_id: str = Depends(verify_bearer_token),
) -> dict:
    # TODO - add workflow_trigger table to track all executions
    logger.info("Running workflow", extra={"workflow_id": workflow_id})
    context_manager = ContextManager.get_instance()
    workflowstore = WorkflowStore()
    workflowmanager = WorkflowManager()
    workflow = workflowstore.get_workflow(workflow_id=workflow_id, tenant_id=tenant_id)
    # Update the context manager with the workflow context
    if body:
        context_manager.update_full_context(**body)

    # Currently, the run workflow with interval via API is not supported
    workflow.workflow_interval = 0
    # Finally, run it
    try:
        errors = workflowmanager.run(
            workflows=[workflow],
        )
    except Exception as e:
        logger.exception(
            "Failed to run workflow",
            extra={"workflow_id": workflow_id},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run workflow {workflow_id}: {e}",
        )
    logger.info(
        "Workflow ran successfully",
        extra={"workflow_id": workflow_id},
    )
    if any(errors[0]):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run workflow {workflow_id}: {errors}",
        )
    else:
        # TODO - add some workflow_execution id to track the execution
        return {"workflow_id": workflow_id, "status": "sucess"}
