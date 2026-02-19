import time
import logging
from io import StringIO
from uuid import uuid4
from typing import List, Union
from pydantic import ValidationError
from keep.api.models.action import ActionDTO
from keep.api.models.db.action import Action
from keep.api.core.db import get_all_actions, create_actions, delete_action, get_action, update_action
from keep.actions.actions_exception import ActionsCRUDException
from keep.functions import cyaml

logger = logging.getLogger(__name__)

class ActionsCRUD:
    """CRUD for Action model that shares across CLI, API, ..."""
    @staticmethod
    def get_all_actions(tenant_id: str) -> List[ActionDTO]:
        action_models = get_all_actions(tenant_id)
        return ActionsCRUD._convert_models_to_dtos(action_models)

    @staticmethod
    def _convert_models_to_dtos(models: List[Action]) -> List[ActionDTO]:
        """Convert model to dto, ignore the result if one model is invalid"""
        results: List[ActionDTO] = []
        for model in models:
            try:
                dto = ActionDTO(id=model.id, use=model.use, name=model.name, details=cyaml.safe_load(StringIO(model.action_raw)))
                results.append(dto)
            except ValidationError:
                logger.warning("Unmatched Action model and the coresponding DTO", exc_info=True, extra={
                    "data": model.dict()
                })
        return results

    @staticmethod
    def add_actions(tenant_id: str, installed_by: str, action_dtos: List[dict]):
        try:
            actions = []
            for action_dto in action_dtos:
                action = Action(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    installed_by=installed_by,
                    installation_time=time.time(),
                    name=action_dto.get("name"),
                    use=action_dto.get("use") or action_dto.get("name"), # if there is no `use` tag, use `name` instead
                    action_raw=cyaml.dump(action_dto)
                )
                actions.append(action)
            create_actions(actions)
        except Exception:
            logger.exception("Failed to create actions")
            raise ActionsCRUDException(status_code=422, detail="Unable to create the actions")

    @staticmethod
    def remove_action(tenant_id: str, action_id: str):
        try:
            deleted_action = delete_action(tenant_id, action_id)
            return deleted_action
        except Exception:
            logger.exception("Unknown exception when delete action from database")
            raise ActionsCRUDException(status_code=422, detail="Unable to delete the requested action")

    @staticmethod
    def get_action(tenant_id: str, action_id: str) -> Union[Action, None]:
        try:
            return get_action(tenant_id, action_id)
        except Exception:
            logger.exception("Unknown exception when getting action from database")
            raise ActionsCRUDException(status_code=400, detail="Unable to get an action")

    @staticmethod
    def update_action(tenant_id: str, action_id: str, payload: dict) -> Union[Action, None]:
        try:
            action_payload = Action(
                name=payload.get("name"),
                use=payload.get("use") or payload.get("name"),
                action_raw=cyaml.dump(payload)
            )
            updated_action = update_action(tenant_id, action_id, action_payload)
            if updated_action:
                return update_action
            raise ActionsCRUDException(status_code=422, detail="No action matched to be updated")
        except Exception:
            logger.exception("Uknown exception when update an action on database")
            raise ActionsCRUDException(status_code=400, detail="Unable to update an action")
