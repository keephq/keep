import logging
from dataclasses import asdict
from functools import reduce
from typing import Any, Dict, List, Optional

import jwt
import yaml
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile

from keep.api.core.db import get_installed_providers, get_workflow_executions
from keep.api.core.dependencies import verify_bearer_token
from keep.api.models.workflow import ProviderDTO, WorkflowDTO, WorkflowExecutionDTO
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser
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
    parser = Parser()
    workflows_dto = []
    # get all workflows
    workflows = workflowstore.get_all_workflows(tenant_id=tenant_id)
    # iterate workflows
    for _workflow in workflows:
        # extract the providers
        workflow, workflow_last_run_time, workflow_last_run_status = _workflow
        workflow_yaml = yaml.safe_load(workflow.workflow_raw)
        providers = parser.get_providers_from_workflow(workflow_yaml)
        installed_providers = get_installed_providers(tenant_id)
        installed_providers = {
            provider.name: provider for provider in installed_providers
        }
        providers_dto = []
        # get the provider details
        for provider in providers:
            try:
                provider = installed_providers[provider.get("name")]
                provider_dto = ProviderDTO(
                    name=provider.name,
                    type=provider.type,
                    id=provider.id,
                    installed=True,
                )
                providers_dto.append(provider_dto)
            except KeyError:
                # the provider is not installed
                provider_dto = ProviderDTO(
                    name=provider.get("name"),
                    type=provider.get("type"),
                    id=None,
                    installed=False,
                )
                providers_dto.append(provider_dto)

        triggers = parser.get_triggers_from_workflow(workflow_yaml)
        # create the workflow DTO
        workflow_dto = WorkflowDTO(
            id=workflow.id,
            description=workflow.description,
            created_by=workflow.created_by,
            creation_time=workflow.creation_time,
            last_execution_time=workflow_last_run_time,
            last_execution_status=workflow_last_run_status,
            interval=workflow.interval,
            providers=providers_dto,
            triggers=triggers,
        )
        workflows_dto.append(workflow_dto)
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
    logger.info("Running workflow", extra={"workflow_id": workflow_id})
    workflowstore = WorkflowStore()
    workflowmanager = WorkflowManager.get_instance()
    workflow = workflowstore.get_workflow(workflow_id=workflow_id, tenant_id=tenant_id)
    # Update the context manager with the workflow context
    # TODO THIS SHOULD NOT WORK
    context_manager = ContextManager(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )
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


@router.post(
    "",
    description="Create a workflow",
)
async def create_workflow(
    request: Request,
    file: UploadFile = File(...),
    tenant_id: str = Depends(verify_bearer_token),
) -> dict:
    try:
        # we support both File upload (from frontend) or raw yaml (e.g. curl)
        if file:
            workflow_raw_data = await file.read()
        else:
            workflow_raw_data = await request.body()
        workflow_data = yaml.safe_load(workflow_raw_data)
        # backward comptability
        if "alert" in workflow_data:
            workflow = workflow_data.pop("alert")
        #
        else:
            workflow = workflow_data.pop("workflow")

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail="Invalid YAML format")

    token = request.headers.get("Authorization").split(" ")[1]
    decoded_token = jwt.decode(token, options={"verify_signature": False})
    created_by = decoded_token.get("email")
    workflowstore = WorkflowStore()
    # Create the workflow
    workflow = workflowstore.create_workflow(
        tenant_id=tenant_id, created_by=created_by, workflow=workflow
    )
    return {"workflow_id": workflow.id, "status": "created"}


@router.get("/{workflow_id}", description="Get workflow executions by ID")
def get_workflow_by_id(
    workflow_id: str,
    tenant_id: str = Depends(verify_bearer_token),
) -> List[WorkflowExecutionDTO]:
    workflow_executions = get_workflow_executions(tenant_id, workflow_id)
    workflow_executions_dtos = []
    for workflow_execution in workflow_executions:
        workflow_execution_dto = WorkflowExecutionDTO(
            id=workflow_execution.id,
            workflow_id=workflow_execution.workflow_id,
            status=workflow_execution.status,
            started=workflow_execution.started,
            triggered_by=workflow_execution.triggered_by,
            error=workflow_execution.error,
            execution_time=workflow_execution.execution_time,
        )
        workflow_executions_dtos.append(workflow_execution_dto)

    return workflow_executions_dtos


@router.delete("/{workflow_id}", description="Delete workflow")
def delete_workflow_by_id(
    workflow_id: str,
    tenant_id: str = Depends(verify_bearer_token),
):
    workflowstore = WorkflowStore()
    workflowstore.delete_workflow(workflow_id=workflow_id, tenant_id=tenant_id)
    return {"workflow_id": workflow_id, "status": "deleted"}
