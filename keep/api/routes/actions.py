import yaml
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile
from fastapi.responses import JSONResponse

from keep.api.core.dependencies import AuthenticatedEntity, AuthVerifier
from keep.actions.actions_factory import ActionsFactory
from keep.actions.actions_exception import ActionsFactoryException

logger = logging.getLogger(__name__)
router = APIRouter()


# GET all actions
@router.get("", description="Get all actions")
def get_actions(
    authenticated_entity: AuthenticatedEntity = Depends(AuthVerifier(["read:actions"])),
):
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting installed actions", extra={tenant_id: tenant_id})

    actions = ActionsFactory.get_all_actions(tenant_id)
    try:
        return actions
    except Exception as e:
        logger.exception("Failed to get actions", extra={
            "error": str(e)
        })
        return []


async def _get_action_info(request: Request, file: UploadFile) -> dict:
    """"Get action data either from file io or form data"""
    try:
        if file:
            action_inforaw = await file.read()
        else:
            action_inforaw = await request.body()
        action_info = yaml.safe_load(action_inforaw)
    except yaml.YAMLError:
        logger.exception("Invalid YAML format when parsing actions file")
        raise HTTPException(status_code=400, detail="Invalid yaml format")
    return action_info

# POST actions
@router.post("", description="Create new actions by uploading a file", status_code=status.HTTP_201_CREATED)
async def create_actions(
    request: Request,
    file: UploadFile = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    installed_by = authenticated_entity.email
    actions_dict = await _get_action_info(request, file)
    try:
        ActionsFactory.add_actions(tenant_id, installed_by, actions_dict.get("actions", []))
        return {"message": "success"}
    except ActionsFactoryException as e:
        return JSONResponse(status_code=e.status_code, content=e.message)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to create action", "error": str(e)},
        )


# DELETE an action
@router.delete("/{action_id}", description="Delete an action")
def delete_action(
    action_id: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    try:
        return ActionsFactory.remove_action(tenant_id, action_id)
    except ActionsFactoryException as e:
        return JSONResponse(status_code=e.status_code, content=e.message)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to delete the action", "error": str(e)},
        )


# UPDATE an action
@router.put("/{action_id}", description="Update an action")
async def put_action(
    action_id: str,
    request: Request,
    file: UploadFile,
    authenticated_entity: AuthenticatedEntity = Depends(
        AuthVerifier(["write:actions"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    try:
        action_dict: dict = await _get_action_info(request, file)
        updated_action = ActionsFactory.update_action(
            tenant_id, action_id, action_dict
        )
        if updated_action:
            return updated_action
        return JSONResponse(status_code=204, content={"message": "No content"})
    except ActionsFactoryException as e:
        return JSONResponse(status_code=e.status_code, content=e.message)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to update the action", "error": str(e)},
        )
