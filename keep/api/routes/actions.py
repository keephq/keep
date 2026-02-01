import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from keep.actions.actions_factory import ActionsCRUD
from keep.functions import cyaml
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

logger = logging.getLogger(__name__)
router = APIRouter()


# GET all actions
@router.get("", description="Get all actions")
def get_actions(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting installed actions", extra={"tenant_id": tenant_id})

    actions = ActionsCRUD.get_all_actions(tenant_id)
    try:
        return actions
    except Exception:
        logger.exception("Failed to get actions")
        raise HTTPException(
            status_code=400, detail="Unknown exception when getting actions"
        )


async def _get_action_info(request: Request, file: UploadFile) -> dict:
    """ "Get action data either from file io or form data"""
    try:
        if file:
            action_inforaw = await file.read()
        else:
            action_inforaw = await request.body()
        action_info = cyaml.safe_load(action_inforaw)
    except cyaml.YAMLError:
        logger.exception("Invalid YAML format when parsing actions file")
        raise HTTPException(status_code=400, detail="Invalid yaml format")
    return action_info


# POST actions
@router.post(
    "",
    description="Create new actions by uploading a file",
    status_code=status.HTTP_201_CREATED,
)
async def create_actions(
    request: Request,
    file: UploadFile = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    installed_by = authenticated_entity.email
    actions_dict = await _get_action_info(request, file)
    ActionsCRUD.add_actions(tenant_id, installed_by, actions_dict.get("actions", []))
    return {"message": "success"}


# DELETE an action
@router.delete("/{action_id}", description="Delete an action")
def delete_action(
    action_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    return ActionsCRUD.remove_action(tenant_id, action_id)


# UPDATE an action
@router.put("/{action_id}", description="Update an action")
async def put_action(
    action_id: str,
    request: Request,
    file: UploadFile,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    action_dict: dict = await _get_action_info(request, file)
    updated_action = ActionsCRUD.update_action(tenant_id, action_id, action_dict)
    if updated_action:
        return updated_action
    return JSONResponse(status_code=204, content={"message": "No content"})
