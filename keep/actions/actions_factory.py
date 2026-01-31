import time
import logging
from io import StringIO
from uuid import uuid4
from typing import List, Optional

from pydantic import ValidationError

from keep.api.models.action import ActionDTO
from keep.api.models.db.action import Action
from keep.api.core.db import (
    get_all_actions as db_get_all_actions,
    create_actions as db_create_actions,
    delete_action as db_delete_action,
    get_action as db_get_action,
    update_action as db_update_action,
)
from keep.actions.actions_exception import ActionsCRUDException
from keep.functions import cyaml

logger = logging.getLogger(__name__)


class ActionsCRUD:
    """CRUD for Action model shared across CLI, API, etc."""

    @staticmethod
    def get_all_actions(tenant_id: str) -> List[ActionDTO]:
        action_models = db_get_all_actions(tenant_id)
        return ActionsCRUD._convert_models_to_dtos(action_models)

    @staticmethod
    def _convert_models_to_dtos(models: List[Action]) -> List[ActionDTO]:
        """Convert models to DTOs; skip invalid models but log details."""
        results: List[ActionDTO] = []
        for model in models:
            try:
                dto = ActionDTO(
                    id=model.id,
                    use=model.use,
                    name=model.name,
                    details=cyaml.safe_load(StringIO(model.action_raw)),
                )
                results.append(dto)
            except ValidationError:
                logger.warning(
                    "Unmatched Action model and the corresponding DTO",
                    exc_info=True,
                    extra={"data": model.dict()},
                )
        return results

    @staticmethod
    def add_actions(tenant_id: str, installed_by: str, action_dtos: List[dict]) -> None:
        try:
            actions: List[Action] = []
            for action_dto in action_dtos:
                name = action_dto.get("name")
                use = action_dto.get("use") or name  # fallback: use name if no `use` is provided

                action = Action(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    installed_by=installed_by,
                    installation_time=time.time(),
                    name=name,
                    use=use,
                    action_raw=cyaml.dump(action_dto),
                )
                actions.append(action)

            db_create_actions(actions)
        except Exception:
            logger.exception("Failed to create actions")
            raise ActionsCRUDException(status_code=422, detail="Unable to create the actions")

    @staticmethod
    def remove_action(tenant_id: str, action_id: str):
        try:
            return db_delete_action(tenant_id, action_id)
        except Exception:
            logger.exception("Unknown exception when deleting action from database")
            raise ActionsCRUDException(status_code=422, detail="Unable to delete the requested action")

    @staticmethod
    def get_action(tenant_id: str, action_id: str) -> Optional[Action]:
        try:
            return db_get_action(tenant_id, action_id)
        except Exception:
            logger.exception("Unknown exception when getting action from database")
            raise ActionsCRUDException(status_code=400, detail="Unable to get an action")

    @staticmethod
    def update_action(tenant_id: str, action_id: str, payload: dict) -> Optional[Action]:
        """
        Update an action by ID.
        Returns the updated Action model if found/updated; otherwise raises.
        """
        try:
            name = payload.get("name")
            use = payload.get("use") or name

            action_payload = Action(
                name=name,
                use=use,
                action_raw=cyaml.dump(payload),
            )

            updated_action = db_update_action(tenant_id, action_id, action_payload)
            if updated_action:
                return updated_action

            raise ActionsCRUDException(status_code=422, detail="No action matched to be updated")
        except ActionsCRUDException:
            # Preserve explicit CRUD errors without double-wrapping
            raise
        except Exception:
            logger.exception("Unknown exception when updating an action in the database")
            raise ActionsCRUDException(status_code=400, detail="Unable to update an action")