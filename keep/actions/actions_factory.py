import time
import logging
import yaml
from io import StringIO
from uuid import uuid4
from typing import List, Union
from keep.api.models.action import ActionDTO
from keep.api.models.db.action import Action
from keep.api.core.db import get_all_actions, create_actions, delete_action, get_action, update_action
from keep.actions.actions_exception import ActionsFactoryException

logger = logging.getLogger(__name__)

class ActionsFactory:
    """CRUD for Action model that shares across CLI, API, ..."""
    @staticmethod
    def get_all_actions(tenant_id: str) -> List[ActionDTO]:
        action_models = get_all_actions(tenant_id)
        action_dtos = map(ActionsFactory._convert_model_to_dto, action_models)
        return list(action_dtos)

    @staticmethod
    def _convert_model_to_dto(model: Action) -> ActionDTO:
        return ActionDTO(
            id=model.id, use=model.use, name=model.name, details=yaml.safe_load(StringIO(model.action_raw))
        )

    @staticmethod
    def add_actions(tenant_id: str, installed_by: str, action_dtos: List[dict]):
        try:
            actions = map(lambda dto: Action(
                id=str(uuid4()),
                tenant_id=tenant_id,
                installed_by=installed_by,
                installation_time=time.time(),
                name=dto.get("name"),
                use=dto.get("use") or dto.get("name"),
                action_raw=yaml.dump(dto)
            ), action_dtos)
            create_actions(actions)
        except Exception as e:
            logger.exception("Failed to create actions", extra={ "error": e })
            raise ActionsFactoryException(status_code=422, message="Unable to create the actions")

    @staticmethod
    def remove_action(tenant_id: str, action_id: str):
        try:
            deleted_action = delete_action(tenant_id, action_id)
            return deleted_action
        except Exception as e:
            logger.error("Unknown exception when delete action from database ", extra={ 
                "error": str(e)
            })
            raise ActionsFactoryException(status_code=422, message="Unable to delete the requested action")

    @staticmethod
    def get_action(tenant_id: str, action_id: str) -> Union[Action, None]:
        try:
            return get_action(tenant_id, action_id)
        except Exception as e:
            logger.error("Unknown exception when getting action from database ", extra={ 
                "error": str(e)
            })
            raise ActionsFactoryException(status_code=400, message="Unable to get an action")

    @staticmethod
    def update_action(tenant_id: str, action_id: str, payload: dict) -> Union[Action, None]:
        try:
            action_payload = Action(
                name=payload.get("name"),
                use=payload.get("use") or payload.get("name"),
                action_raw=yaml.dump(payload)
            )
            updated_action = update_action(tenant_id, action_id, action_payload)
            if updated_action:
                return update_action
            raise ActionsFactoryException(status_code=422, message="No action matched to be updated")
        except Exception as e:
            logger.error("Uknown exception when update an action on database", extra={
                "error": str(e)
            })
            raise ActionsFactoryException(status_code=400, message="Unable to update an action")