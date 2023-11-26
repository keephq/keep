import logging
from typing import Any, Dict, List, Optional

import validators
import yaml
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlmodel import Session

from keep.api.core.db import (
    get_installed_providers,
    get_last_workflow_executions,
    get_session,
    get_workflow,
)
from keep.api.core.db import get_workflow_executions as get_workflow_executions_db
from keep.api.core.db import get_workflow_id_by_name
from keep.api.core.dependencies import (
    get_user_email,
    verify_bearer_token,
    verify_token_or_key,
)
from keep.api.models.workflow import (
    ProviderDTO,
    WorkflowCreateOrUpdateDTO,
    WorkflowDTO,
    WorkflowExecutionDTO,
    WorkflowExecutionLogsDTO,
)
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.workflowmanager.workflowstore import WorkflowStore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    description="Get workflows",
)
def get_workflows(
    tenant_id: str = Depends(verify_token_or_key),
) -> list[WorkflowDTO]:
    workflowstore = WorkflowStore()
    parser = Parser()
    workflows_dto = []
    installed_providers = get_installed_providers(tenant_id)
    installed_providers_by_type = {}
    for installed_provider in installed_providers:
        if installed_provider.type not in installed_providers_by_type:
            installed_providers_by_type[installed_provider.type] = {
                installed_provider.name: installed_provider
            }
        else:
            installed_providers_by_type[installed_provider.type][
                installed_provider.name
            ] = installed_provider
    # get all workflows
    workflows = workflowstore.get_all_workflows_with_last_execution(tenant_id=tenant_id)
    # iterate workflows
    for _workflow in workflows:
        # extract the providers
        workflow, workflow_last_run_time, workflow_last_run_status = _workflow
        workflow_yaml = yaml.safe_load(workflow.workflow_raw)
        providers = parser.get_providers_from_workflow(workflow_yaml)
        providers_dto = []
        # get the provider details
        for provider in providers:
            try:
                provider = installed_providers_by_type[provider.get("type")][
                    provider.get("name")
                ]
                provider_dto = ProviderDTO(
                    name=provider.name,
                    type=provider.type,
                    id=provider.id,
                    installed=True,
                )
                providers_dto.append(provider_dto)
            except KeyError:
                # the provider is not installed, now we want to check:
                # 1. if the provider requires any config - so its not instaleld
                # 2. if the provider does not require any config - consider it as installed
                conf = ProvidersFactory.get_provider_required_config(
                    provider.get("type")
                )
                if conf:
                    provider_dto = ProviderDTO(
                        name=provider.get("name"),
                        type=provider.get("type"),
                        id=None,
                        installed=False,
                    )
                # if the provider does not require any config, consider it as installed
                else:
                    provider_dto = ProviderDTO(
                        name=provider.get("name"),
                        type=provider.get("type"),
                        id=None,
                        installed=True,
                    )
                providers_dto.append(provider_dto)

        triggers = parser.get_triggers_from_workflow(workflow_yaml)
        # create the workflow DTO
        workflow_dto = WorkflowDTO(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description or "[This workflow has no description]",
            created_by=workflow.created_by,
            creation_time=workflow.creation_time,
            last_execution_time=workflow_last_run_time,
            last_execution_status=workflow_last_run_status,
            interval=workflow.interval,
            providers=providers_dto,
            triggers=triggers,
            workflow_raw=workflow.workflow_raw,
            revision=workflow.revision,
            last_updated=workflow.last_updated,
        )
        workflows_dto.append(workflow_dto)
    return workflows_dto


@router.post(
    "/{workflow_id}/run",
    description="Run a workflow",
)
def run_workflow(
    workflow_id: str,
    body: Optional[Dict[Any, Any]] = Body(None),
    tenant_id: str = Depends(verify_token_or_key),
    created_by: str = Depends(get_user_email),
) -> dict:
    logger.info("Running workflow", extra={"workflow_id": workflow_id})
    # if the workflow id is the name of the workflow (e.g. the CLI has only the name)
    if not validators.uuid(workflow_id):
        logger.info("Workflow ID is not a UUID, trying to get the ID by name")
        workflow_id = get_workflow_id_by_name(tenant_id, workflow_id)
    workflowmanager = WorkflowManager.get_instance()

    # Finally, run it
    try:
        workflow_execution_id = workflowmanager.scheduler.handle_manual_event_workflow(
            workflow_id, tenant_id, created_by, "manual", body
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
        extra={
            "workflow_id": workflow_id,
        },
    )
    return {
        "workflow_id": workflow_id,
        "workflow_execution_id": workflow_execution_id,
        "status": "success",
    }


async def __get_workflow_raw_data(request: Request, file: UploadFile) -> dict:
    try:
        # we support both File upload (from frontend) or raw yaml (e.g. curl)
        if file:
            workflow_raw_data = await file.read()
        else:
            workflow_raw_data = await request.body()
        workflow_data = yaml.safe_load(workflow_raw_data)
        # backward comptability
        if "alert" in workflow_data:
            workflow_data = workflow_data.pop("alert")
        #
        elif "workflow" in workflow_data:
            workflow_data = workflow_data.pop("workflow")

    except yaml.YAMLError:
        raise HTTPException(status_code=400, detail="Invalid YAML format")
    return workflow_data


@router.post(
    "", description="Create or update a workflow", status_code=status.HTTP_201_CREATED
)
async def create_workflow(
    request: Request,
    file: UploadFile = None,
    tenant_id: str = Depends(verify_token_or_key),
    created_by: str = Depends(get_user_email),
) -> WorkflowCreateOrUpdateDTO:
    workflow = await __get_workflow_raw_data(request, file)
    workflowstore = WorkflowStore()
    # Create the workflow
    workflow = workflowstore.create_workflow(
        tenant_id=tenant_id, created_by=created_by, workflow=workflow
    )
    if workflow.revision == 1:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="created", revision=workflow.revision
        )
    else:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="updated", revision=workflow.revision
        )


@router.put(
    "/{workflow_id}",
    description="Update a workflow",
    status_code=status.HTTP_201_CREATED,
)
async def update_workflow_by_id(
    workflow_id: str,
    request: Request,
    tenant_id: str = Depends(verify_bearer_token),
    session: Session = Depends(get_session),
) -> WorkflowCreateOrUpdateDTO:
    """
    Update a workflow

    Args:
        workflow_id (str): The workflow ID
        request (Request): The FastAPI Request object
        file (UploadFile, optional): File if was uploaded via file. Defaults to File(...).
        tenant_id (str, optional): The tenant ID. Defaults to Depends(verify_bearer_token).
        session (Session, optional): DB Session object injected via DI. Defaults to Depends(get_session).

    Raises:
        HTTPException: If the workflow was not found

    Returns:
        Workflow: The updated workflow
    """
    logger.info(f"Updating workflow {workflow_id}", extra={"tenant_id": tenant_id})
    workflow_from_db = get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if not workflow_from_db:
        logger.warning(
            f"Tenant tried to update workflow {workflow_id} that does not exist",
            extra={"tenant_id": tenant_id},
        )
        raise HTTPException(404, "Workflow not found")
    workflow = await __get_workflow_raw_data(request, None)
    parser = Parser()
    workflow_interval = parser.parse_interval(workflow)
    workflow_from_db.description = workflow.get("description")
    workflow_from_db.interval = workflow_interval
    workflow_from_db.workflow_raw = yaml.dump(workflow)
    session.add(workflow_from_db)
    session.commit()
    session.refresh(workflow_from_db)
    logger.info(f"Updated workflow {workflow_id}", extra={"tenant_id": tenant_id})
    return WorkflowCreateOrUpdateDTO(workflow_id=workflow_id, status="updated")


@router.get("/{workflow_id}/raw", description="Get workflow executions by ID")
def get_raw_workflow_by_id(
    workflow_id: str,
    tenant_id: str = Depends(verify_bearer_token),
) -> str:
    workflowstore = WorkflowStore()
    return JSONResponse(
        status_code=200,
        content={
            "workflow_raw": workflowstore.get_raw_workflow(
                tenant_id=tenant_id, workflow_id=workflow_id
            )
        },
    )


@router.get("/{workflow_id}", description="Get workflow executions by ID")
def get_workflow_by_id(
    workflow_id: str,
    tenant_id: str = Depends(verify_bearer_token),
) -> List[WorkflowExecutionDTO]:
    workflow_executions = get_workflow_executions_db(tenant_id, workflow_id)
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
            results=workflow_execution.results,
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


@router.get(
    "/{workflow_id}/runs/{workflow_execution_id}",
    description="Get a workflow execution status",
)
def get_workflow_execution_status(
    workflow_id: str,
    workflow_execution_id: str,
    tenant_id: str = Depends(verify_bearer_token),
) -> WorkflowExecutionDTO:
    workflowstore = WorkflowStore()
    workflow_execution = workflowstore.get_workflow_execution(
        workflow_execution_id=workflow_execution_id,
        tenant_id=tenant_id,
    )
    workflow_execution_dto = WorkflowExecutionDTO(
        id=workflow_execution.id,
        workflow_id=workflow_execution.workflow_id,
        status=workflow_execution.status,
        started=workflow_execution.started,
        triggered_by=workflow_execution.triggered_by,
        error=workflow_execution.error,
        execution_time=workflow_execution.execution_time,
        logs=[
            WorkflowExecutionLogsDTO(
                id=log.id,
                timestamp=log.timestamp,
                message=log.message,
                context=log.context if log.context else {},
            )
            for log in workflow_execution.logs
        ],
        results=workflow_execution.results,
    )
    return workflow_execution_dto


# todo: move to better URL
# I can't use "/executions" since we already have "/{workflow_id}" endpoint
@router.get(
    "/executions/list",
    description="List last workflow executions",
)
def get_workflow_executions(
    tenant_id: str = Depends(verify_token_or_key),
    workflow_execution_id: Optional[str] = Query(
        None, description="Workflow execution ID"
    ),
) -> List[WorkflowExecutionDTO]:
    # if specific execution
    if workflow_execution_id:
        workflowstore = WorkflowStore()
        workflow_executions = [
            workflowstore.get_workflow_execution(
                workflow_execution_id=workflow_execution_id,
                tenant_id=tenant_id,
            )
        ]
    else:
        workflow_executions = get_last_workflow_executions(tenant_id=tenant_id)
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
            logs=[
                WorkflowExecutionLogsDTO(
                    id=log.id,
                    timestamp=log.timestamp,
                    message=log.message,
                    context=log.context if log.context else {},
                )
                for log in workflow_execution.logs
            ],
            results=workflow_execution.results,
        )
        workflow_executions_dtos.append(workflow_execution_dto)
    return workflow_executions_dtos
