import datetime
import logging
import os
from typing import Any, Dict, List, Optional

import validators
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
from fastapi.responses import JSONResponse, RedirectResponse
from opentelemetry import trace
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import (
    get_alert_by_event_id,
    get_installed_providers,
    get_last_workflow_workflow_to_alert_executions,
    get_session,
    get_workflow,
    get_workflow_by_name,
)
from keep.api.core.db import get_workflow_executions as get_workflow_executions_db
from keep.api.core.workflows import get_workflow_facets, get_workflow_facets_data
from keep.api.models.alert import AlertDto, IncidentDto
from keep.api.models.facet import FacetOptionsQueryDto
from keep.api.models.workflow import (
    WorkflowCreateOrUpdateDTO,
    WorkflowDTO,
    WorkflowExecutionDTO,
    WorkflowExecutionLogsDTO,
    WorkflowToAlertExecutionDTO,
)
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.api.utils.pagination import WorkflowExecutionsPaginatedResultsDto
from keep.functions import cyaml
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.parser.parser import Parser
from keep.workflowmanager.workflowmanager import WorkflowManager
from keep.workflowmanager.workflowstore import WorkflowStore

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

PLATFORM_URL = config("KEEP_PLATFORM_URL", default="https://platform.keephq.dev")


@router.post(
    "/facets/options",
    description="Query alert facet options. Accepts dictionary where key is facet id and value is cel to query facet",
)
def fetch_facet_options(
    facet_options_query: FacetOptionsQueryDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching workflow facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    facet_options = get_workflow_facets_data(
        tenant_id=tenant_id, facet_options_query=facet_options_query
    )

    logger.info(
        "Fetched workflow facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facet_options


@router.get(
    "/facets",
    description="Get workflow facets",
)
def fetch_facets(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> list:
    tenant_id = authenticated_entity.tenant_id

    logger.info(
        "Fetching workflow facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    facets = get_workflow_facets(tenant_id=tenant_id)

    logger.info(
        "Fetched workflow facets from DB",
        extra={
            "tenant_id": tenant_id,
        },
    )

    return facets


# @router.get(
#     "/facets/fields",
#     description="Get potential fields for alert facets",
# )
# def fetch_alert_facet_fields(
#     authenticated_entity: AuthenticatedEntity = Depends(
#     IdentityManagerFactory.get_auth_verifier(["read:workflows"])
# ),
# ) -> list:
#     tenant_id = authenticated_entity.tenant_id

#     logger.info(
#         "Fetching alert facet fields from DB",
#         extra={
#             "tenant_id": tenant_id,
#         },
#     )

#     fields = get_alert_potential_facet_fields(tenant_id=tenant_id)

#     logger.info(
#         "Fetched alert facet fields from DB",
#         extra={
#             "tenant_id": tenant_id,
#         },
#     )
#     return fields

# Redesign the workflow Card
#   The workflow card needs execution records (currently limited to 15) for the graph. To achieve this, the following changes
#   were made in the backend:
#   1. Query Search Parameter: A new query search parameter called is_v2 has been added, which accepts a boolean
#     (default is false).
#   2. Grouped Workflow Executions: When a request is made with /workflows?is_v2=true, workflow executions are grouped
#      by workflow.id.
#   3. Response Updates: The response includes the following new keys and their respective information:
#       -> last_executions: Used for the workflow execution graph.
#       ->last_execution_started: Used for showing the start time of execution in real-time.
@router.get(
    "",
    description="Get workflows",
)
def get_workflows(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
    is_v2: Optional[bool] = Query(False, alias="is_v2", type=bool),
    cel=Query(None),
    limit: int = Query(1000),
    offset: int = Query(0),
    sort_by=Query(None),
    sort_dir=Query(None),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
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
    workflows, count = workflowstore.get_all_workflows_with_last_execution(
        tenant_id=tenant_id,
        cel=cel,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
        is_v2=is_v2,
    )

    # Group last workflow executions by workflow
    if is_v2:
        workflows = workflowstore.group_last_workflow_executions(workflows=workflows)

    # iterate workflows
    for _workflow in workflows:
        # extract the providers
        if is_v2:
            workflow = _workflow["workflow"]
            workflow_last_run_time = _workflow["workflow_last_run_time"]
            workflow_last_run_status = _workflow["workflow_last_run_status"]
            last_executions = _workflow["workflow_last_executions"]
            last_execution_started = _workflow["workflow_last_run_started"]
        else:
            workflow, workflow_last_run_time, workflow_last_run_status = _workflow
            last_executions = None
            last_execution_started = None

        try:
            providers_dto, triggers = workflowstore.get_workflow_meta_data(
                tenant_id=tenant_id,
                workflow=workflow,
                installed_providers_by_type=installed_providers_by_type,
            )
        except Exception as e:
            logger.error(f"Error fetching workflow meta data: {e}")
            providers_dto, triggers = [], []  # Default in case of failure

        # create the workflow DTO
        try:
            workflow_raw = cyaml.safe_load(workflow.workflow_raw)
            is_alert_rule_worfklow = WorkflowStore.is_alert_rule_workflow(workflow_raw)
            # very big width to avoid line breaks
            workflow_raw = cyaml.dump(workflow_raw, width=99999)
            workflow_dto = WorkflowDTO(
                id=workflow.id,
                name=workflow.name,
                description=workflow.description
                or "[This workflow has no description]",
                created_by=workflow.created_by,
                creation_time=workflow.creation_time,
                last_execution_time=workflow_last_run_time,
                last_execution_status=workflow_last_run_status,
                interval=workflow.interval,
                providers=providers_dto,
                triggers=triggers,
                workflow_raw=workflow_raw,
                revision=workflow.revision,
                last_updated=workflow.last_updated,
                last_executions=last_executions,
                last_execution_started=last_execution_started,
                disabled=workflow.is_disabled,
                provisioned=workflow.provisioned,
                alertRule=is_alert_rule_worfklow,
            )
        except Exception as e:
            logger.error(f"Error creating workflow DTO: {e}")
            continue
        workflows_dto.append(workflow_dto)
    return {
        "count": count,
        "results": workflows_dto,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/export",
    description="export all workflow Yamls",
)
def export_workflows(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> list[str]:
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
    # get all workflows
    workflows = workflowstore.get_all_workflows_yamls(tenant_id=tenant_id)
    return workflows


@router.post(
    "/{workflow_id}/run",
    description="Run a workflow",
)
def run_workflow(
    workflow_id: str,
    event_type: Optional[str] = Query(None),
    event_id: Optional[str] = Query(None),
    body: Optional[Dict[Any, Any]] = Body(None),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    created_by = authenticated_entity.email
    logger.info("Running workflow", extra={"workflow_id": workflow_id})

    workflow = get_workflow(tenant_id, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found",
        )

    # if the workflow id is the name of the workflow (e.g. the CLI has only the name)
    if not validators.uuid(workflow_id):
        logger.info("Workflow ID is not a UUID, trying to get the ID by name")
        workflow_id = getattr(get_workflow_by_name(tenant_id, workflow_id), "id", None)

    workflowmanager = WorkflowManager.get_instance()

    try:
        # Handle replay from query parameters
        if event_type and event_id:
            if event_type == "alert":
                # Fetch alert from your alert store
                alert_db = get_alert_by_event_id(tenant_id, event_id)
                event = convert_db_alerts_to_dto_alerts([alert_db])[0]
            elif event_type == "incident":
                # SHAHAR: TODO
                raise NotImplementedError("Incident replay is not supported yet")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid event type: {event_type}",
                )
        else:
            # Handle regular run from body
            event_body = body.get("body", {}) or body
            event_class = (
                AlertDto if body.get("type", "alert") == "alert" else IncidentDto
            )

            # Handle UI triggered events
            fingerprint = event_body.get("fingerprint", "")
            if (fingerprint and "test-workflow" in fingerprint) or not body:
                event_body["id"] = event_body.get("fingerprint", "manual-run")
                event_body["name"] = event_body.get("fingerprint", "manual-run")
                event_body["lastReceived"] = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
                if "source" in event_body and not isinstance(
                    event_body["source"], list
                ):
                    event_body["source"] = [event_body["source"]]

            try:
                event = event_class(**event_body)
            except TypeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid event format",
                )

        workflow_execution_id = workflowmanager.scheduler.handle_manual_event_workflow(
            workflow_id, tenant_id, created_by, event
        )
    except Exception as e:
        logger.exception(
            "Failed to run workflow",
            extra={
                "workflow_id": workflow_id,
                "tenant_id": tenant_id,
            },
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


@router.get("/{workflow_id}/run", description="Run a workflow")
def run_workflow_with_query_params(
    workflow_id: str,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
):
    params = dict(request.query_params)

    alert_id = params.get("alert", params.get("alert_id"))
    if params.get("alert", params.get("alert_id")):
        response = run_workflow(
            workflow_id,
            "alert",
            alert_id,
            params,
            authenticated_entity,
        )
    else:
        response = run_workflow(workflow_id, None, None, params, authenticated_entity)
    if response.get("status") == "success":
        workflow_execution_id = response.get("workflow_execution_id")
        return RedirectResponse(
            url=f"{PLATFORM_URL}/workflows/{workflow_id}/runs/{workflow_execution_id}"
        )
    else:
        return RedirectResponse(
            url=f"{PLATFORM_URL}/workflows/{workflow_id}?error=failed_to_run_workflow"
        )


@router.post(
    "/test",
    description="Test run a workflow from a definition",
)
async def run_workflow_from_definition(
    request: Request,
    file: UploadFile = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    created_by = authenticated_entity.email
    workflow = await __get_workflow_raw_data(request, file)
    workflowstore = WorkflowStore()
    workflowmanager = WorkflowManager.get_instance()
    try:
        workflow = workflowstore.get_workflow_from_dict(
            tenant_id=tenant_id, workflow=workflow
        )
    except Exception as e:
        logger.exception(
            "Failed to parse workflow",
            extra={"tenant_id": tenant_id, "workflow": workflow},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse test workflow: {e}",
        )

    try:
        workflow_execution = workflowmanager.scheduler.handle_workflow_test(
            workflow, tenant_id, created_by
        )
    except Exception as e:
        logger.exception(
            "Failed to run test workflow",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run test workflow: {e}",
        )
    logger.info(
        "Workflow ran successfully",
        extra={"workflow_execution": workflow_execution},
    )
    # TODO: return the workflow execution DTO, or at least logs, so results can be shown in the UI
    return workflow_execution


async def __get_workflow_raw_data(request: Request, file: UploadFile | None) -> dict:
    try:
        # we support both File upload (from frontend) or raw yaml (e.g. curl)
        if file:
            workflow_raw_data = await file.read()
        else:
            workflow_raw_data = await request.body()
        workflow_data = cyaml.safe_load(workflow_raw_data)
        # backward comptability
        if "alert" in workflow_data:
            workflow_data = workflow_data.pop("alert")
        #
        elif "workflow" in workflow_data:
            workflow_data = workflow_data.pop("workflow")

    except cyaml.YAMLError:
        logger.exception("Invalid YAML format")
        raise HTTPException(status_code=400, detail="Invalid YAML format")
    return workflow_data


@router.post(
    "", description="Create or update a workflow", status_code=status.HTTP_201_CREATED
)
async def create_workflow(
    file: UploadFile,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
) -> WorkflowCreateOrUpdateDTO:
    tenant_id = authenticated_entity.tenant_id
    created_by = authenticated_entity.email
    workflow = await __get_workflow_raw_data(request=None, file=file)
    workflowstore = WorkflowStore()
    # Create the workflow
    try:
        workflow = workflowstore.create_workflow(
            tenant_id=tenant_id, created_by=created_by, workflow=workflow
        )
    except Exception:
        logger.exception(
            "Failed to create workflow",
            extra={"tenant_id": tenant_id, "workflow": workflow},
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to upload workflow. Please contact us via Slack for help.",
        )
    if workflow.revision == 1:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="created", revision=workflow.revision
        )
    else:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="updated", revision=workflow.revision
        )


@router.get("/executions", description="Get workflow executions by alert fingerprint")
def get_workflow_executions_by_alert_fingerprint(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
    session: Session = Depends(get_session),
) -> list[WorkflowToAlertExecutionDTO]:
    with tracer.start_as_current_span("get_workflow_executions_by_alert_fingerprint"):
        latest_workflow_to_alert_executions = (
            get_last_workflow_workflow_to_alert_executions(
                session=session, tenant_id=authenticated_entity.tenant_id
            )
        )

    return [
        WorkflowToAlertExecutionDTO(
            workflow_id=workflow_execution.workflow_execution.workflow_id,
            workflow_execution_id=workflow_execution.workflow_execution_id,
            alert_fingerprint=workflow_execution.alert_fingerprint,
            workflow_status=workflow_execution.workflow_execution.status,
            workflow_started=workflow_execution.workflow_execution.started,
            event_id=workflow_execution.event_id,
        )
        for workflow_execution in latest_workflow_to_alert_executions
    ]


@router.post(
    "/json",
    description="Create or update a workflow",
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_from_body(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
) -> WorkflowCreateOrUpdateDTO:
    tenant_id = authenticated_entity.tenant_id
    created_by = authenticated_entity.email
    workflow = await __get_workflow_raw_data(request, None)
    workflowstore = WorkflowStore()
    # Create the workflow
    try:
        workflow = workflowstore.create_workflow(
            tenant_id=tenant_id, created_by=created_by, workflow=workflow
        )
    except Exception:
        logger.exception(
            "Failed to create workflow",
            extra={"tenant_id": tenant_id, "workflow": workflow},
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to upload workflow. Please contact us via Slack for help.",
        )
    if workflow.revision == 1:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="created", revision=workflow.revision
        )
    else:
        return WorkflowCreateOrUpdateDTO(
            workflow_id=workflow.id, status="updated", revision=workflow.revision
        )


# Add Mock Workflows (6 Random Workflows on Every Request)
#    To add mock workflows, a new backend API endpoint has been created: /workflows/random-templates.
#      1. Fetching Random Templates: When a request is made to this endpoint, all workflow YAML/YML files are read and
#         shuffled randomly.
#      2. Response: Only the first 6 files are parsed and sent in the response.
@router.get("/random-templates", description="Get random workflow templates")
def get_random_workflow_templates(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> list[dict]:
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
    default_directory = os.environ.get(
        "KEEP_WORKFLOWS_PATH",
        os.path.join(os.path.dirname(__file__), "../../../examples/workflows"),
    )
    if not os.path.exists(default_directory):
        # on the container we use the following path
        fallback_directory = "/examples/workflows"
        logger.warning(
            f"{default_directory} does not exist, using fallback: {fallback_directory}"
        )
        if os.path.exists(fallback_directory):
            default_directory = fallback_directory
        else:
            logger.error(f"Neither {default_directory} nor {fallback_directory} exist")
            raise FileNotFoundError(
                f"Neither {default_directory} nor {fallback_directory} exist"
            )
    workflows = workflowstore.get_random_workflow_templates(
        tenant_id=tenant_id, workflows_dir=default_directory, limit=8
    )
    return workflows


@router.put(
    "/{workflow_id}",
    description="Update a workflow",
    status_code=status.HTTP_201_CREATED,
)
async def update_workflow_by_id(
    workflow_id: str,
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
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
    tenant_id = authenticated_entity.tenant_id
    logger.info(f"Updating workflow {workflow_id}", extra={"tenant_id": tenant_id})
    workflow_from_db = get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if not workflow_from_db:
        logger.warning(
            f"Tenant tried to update workflow {workflow_id} that does not exist",
            extra={"tenant_id": tenant_id},
        )
        raise HTTPException(404, "Workflow not found")

    if workflow_from_db.provisioned:
        raise HTTPException(403, detail="Cannot update a provisioned workflow")

    workflow = await __get_workflow_raw_data(request, None)
    parser = Parser()
    workflow_interval = parser.parse_interval(workflow)
    # In case the workflow name changed to empty string, keep the old name
    if workflow.get("name") != "":
        workflow_from_db.name = workflow.get("name")
    else:
        workflow["name"] = workflow_from_db.name
    workflow_from_db.description = workflow.get("description")
    workflow_from_db.interval = workflow_interval
    workflow_from_db.is_disabled = workflow.get("disabled", False)
    workflow_from_db.workflow_raw = cyaml.dump(workflow, width=99999)
    workflow_from_db.last_updated = datetime.datetime.now()
    session.add(workflow_from_db)
    session.commit()
    session.refresh(workflow_from_db)
    logger.info(f"Updated workflow {workflow_id}", extra={"tenant_id": tenant_id})
    return WorkflowCreateOrUpdateDTO(workflow_id=workflow_id, status="updated")


@router.get("/{workflow_id}/raw", description="Get workflow executions by ID")
def get_raw_workflow_by_id(
    workflow_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> str:
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
    return JSONResponse(
        status_code=200,
        content={
            "workflow_raw": workflowstore.get_raw_workflow(
                tenant_id=tenant_id, workflow_id=workflow_id
            )
        },
    )


@router.get("/{workflow_id}", description="Get workflow by ID")
def get_workflow_by_id(
    workflow_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    # get all workflow
    workflow = get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if not workflow:
        logger.warning(
            f"Tenant tried to get workflow {workflow_id} that does not exist",
            extra={"tenant_id": tenant_id},
        )
        raise HTTPException(404, "Workflow not found")

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

    workflowstore = WorkflowStore()
    try:
        providers_dto, triggers = workflowstore.get_workflow_meta_data(
            tenant_id=tenant_id,
            workflow=workflow,
            installed_providers_by_type=installed_providers_by_type,
        )
    except Exception as e:
        logger.error(f"Error fetching workflow meta data: {e}")
        providers_dto, triggers = [], []  # Default in case of failure

    try:
        workflow_yaml = cyaml.safe_load(workflow.workflow_raw)
        valid_workflow_yaml = {"workflow": workflow_yaml}
        final_workflow_raw = cyaml.dump(valid_workflow_yaml, width=99999)
        workflow_dto = WorkflowDTO(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description or "[This workflow has no description]",
            created_by=workflow.created_by,
            creation_time=workflow.creation_time,
            interval=workflow.interval,
            providers=providers_dto,
            triggers=triggers,
            workflow_raw=final_workflow_raw,
            last_updated=workflow.last_updated,
            disabled=workflow.is_disabled,
        )
        return workflow_dto
    except cyaml.YAMLError:
        logger.exception("Invalid YAML format")
        raise HTTPException(status_code=500, detail="Error fetching workflow meta data")


@router.get("/{workflow_id}/runs", description="Get workflow executions by ID")
def get_workflow_runs_by_id(
    workflow_id: str,
    tab: int = 1,
    limit: int = 25,
    offset: int = 0,
    status: Optional[List[str]] = Query(None),
    trigger: Optional[List[str]] = Query(None),
    execution_id: Optional[str] = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> WorkflowExecutionsPaginatedResultsDto:
    tenant_id = authenticated_entity.tenant_id
    workflow = get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
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

    with tracer.start_as_current_span("get_workflow_executions"):
        total_count, workflow_executions, pass_count, fail_count, avgDuration = (
            get_workflow_executions_db(
                tenant_id,
                workflow_id,
                limit,
                offset,
                tab,
                status,
                trigger,
                execution_id,
            )
        )
    workflow_executions_dtos = []
    with tracer.start_as_current_span("create_workflow_dtos"):
        for workflow_execution in workflow_executions:
            workflow_execution_dto = {
                "id": workflow_execution.id,
                "workflow_id": workflow_execution.workflow_id,
                "status": workflow_execution.status,
                "started": workflow_execution.started.isoformat(),
                "triggered_by": workflow_execution.triggered_by,
                "error": workflow_execution.error,
                "execution_time": workflow_execution.execution_time,
            }
            workflow_executions_dtos.append(workflow_execution_dto)

    workflowstore = WorkflowStore()
    try:
        providers_dto, triggers = workflowstore.get_workflow_meta_data(
            tenant_id=tenant_id,
            workflow=workflow,
            installed_providers_by_type=installed_providers_by_type,
        )
    except Exception as e:
        logger.error(f"Error fetching workflow meta data: {e}")
        providers_dto, triggers = [], []  # Default in case of failure

    final_workflow = WorkflowDTO(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description or "[This workflow has no description]",
        created_by=workflow.created_by,
        creation_time=workflow.creation_time,
        interval=workflow.interval,
        providers=providers_dto,
        triggers=triggers,
        workflow_raw=workflow.workflow_raw,
        last_updated=workflow.last_updated,
        disabled=workflow.is_disabled,
    )
    return WorkflowExecutionsPaginatedResultsDto(
        limit=limit,
        offset=offset,
        count=total_count,
        items=workflow_executions_dtos,
        passCount=pass_count,
        failCount=fail_count,
        avgDuration=avgDuration,
        workflow=final_workflow,
    )


@router.delete("/{workflow_id}", description="Delete workflow")
def delete_workflow_by_id(
    workflow_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:workflows"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
    workflowstore.delete_workflow(workflow_id=workflow_id, tenant_id=tenant_id)
    return {"workflow_id": workflow_id, "status": "deleted"}


@router.get(
    "/{workflow_id}/runs/{workflow_execution_id}",
    description="Get a workflow execution status",
)
def get_workflow_execution_status(
    workflow_execution_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:workflows"])
    ),
) -> WorkflowExecutionDTO:
    tenant_id = authenticated_entity.tenant_id
    workflowstore = WorkflowStore()
    workflow_execution = workflowstore.get_workflow_execution(
        workflow_execution_id=workflow_execution_id,
        tenant_id=tenant_id,
    )

    if not workflow_execution:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow execution {workflow_execution_id} not found",
        )

    event_id = None
    event_type = None

    if workflow_execution.workflow_to_alert_execution:
        event_id = workflow_execution.workflow_to_alert_execution.event_id
        event_type = "alert"
    # TODO: sub triggers? on create? on update?
    elif workflow_execution.workflow_to_incident_execution:
        event_id = workflow_execution.workflow_to_incident_execution.incident_id
        event_type = "incident"

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
        event_id=event_id,
        event_type=event_type,
    )
    return workflow_execution_dto


@router.put(
    "/{workflow_id}/toggle",
    description="Enable or disable a workflow",
)
def toggle_workflow_state(
    workflow_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:workflows"])
    ),
    session: Session = Depends(get_session),
) -> dict:
    """
    Toggle the enabled/disabled state of a workflow

    Args:
        workflow_id (str): The workflow ID
        authenticated_entity (AuthenticatedEntity): The authenticated entity
        session (Session): DB Session object

    Raises:
        HTTPException: If the workflow was not found or if it's provisioned

    Returns:
        dict: Status of the operation
    """
    tenant_id = authenticated_entity.tenant_id
    logger.info(f"Toggling workflow {workflow_id}", extra={"tenant_id": tenant_id})

    workflow = get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if not workflow:
        logger.warning(
            f"Tenant tried to toggle workflow {workflow_id} that does not exist",
            extra={"tenant_id": tenant_id},
        )
        raise HTTPException(404, "Workflow not found")

    if workflow.provisioned:
        raise HTTPException(403, detail="Cannot modify a provisioned workflow")

    # Toggle the disabled state
    workflow.is_disabled = not workflow.is_disabled
    workflow.last_updated = datetime.datetime.now()

    session.add(workflow)
    session.commit()

    logger.info(
        f"Workflow {workflow_id} {'disabled' if workflow.is_disabled else 'enabled'}",
        extra={"tenant_id": tenant_id},
    )

    return {
        "workflow_id": workflow_id,
        "status": "success",
        "is_disabled": workflow.is_disabled,
    }
