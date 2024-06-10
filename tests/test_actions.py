import pytest
import time
from uuid import uuid4
from typing import List

from keep.api.models.db.action import Action
from keep.api.core.db import create_action
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.actions.actions_factory import ActionsFactory
from keep.actions.actions_exception import ActionsFactoryException

NUMBER_OF_SEEDS = 10

@pytest.fixture
def setup_db(db_session):
    for i in range(NUMBER_OF_SEEDS):
        action: Action = Action(
            id=str(uuid4()),
            tenant_id=SINGLE_TENANT_UUID,
            installed_by="pytest",
            installation_time=time.time(),
            name=f"test_{i}",
            use=f"@test_{i}",
            action_raw="",
        )
        create_action(action)


class TestActionFactory:

    @pytest.mark.usefixtures("setup_db")
    def test_get_an_action(self, db_session):
        actions = ActionsFactory.get_all_actions(SINGLE_TENANT_UUID)
        action = ActionsFactory.get_action(SINGLE_TENANT_UUID, actions[0].id)
        assert action is not None

    @pytest.mark.usefixtures("setup_db")
    def test_get_an_action_not_found(self, db_session):
        try:
            action = ActionsFactory.get_action(SINGLE_TENANT_UUID, "test_no_found")
            assert action is None
        except ActionsFactoryException: 
            pytest.fail(pytrace=True, msg="Get an non-exist action should not raise ActionsFactoryException")

    @pytest.mark.usefixtures("setup_db")
    def test_get_all_actions(self, db_session):
        actions = ActionsFactory.get_all_actions(SINGLE_TENANT_UUID)
        assert len(actions) == NUMBER_OF_SEEDS

    def test_create_actions(self, db_session):
        actions: List[dict] = []
        for i in range(NUMBER_OF_SEEDS):
            action = {
                "tenant_id": SINGLE_TENANT_UUID,
                "installed_by": "pytest",
                "installation_time": time.time(),
                "name": f"test_{i}",
                "use": f"@test_{i}",
                "action_raw": "",
            }
            actions.append(action)
        try:
            ActionsFactory.add_actions(SINGLE_TENANT_UUID, "pytest", actions)
        except ActionsFactoryException:
            pytest.fail(
                pytrace=True,
                msg="Adding valid actions should not raise ActionsFactoryException",
            )

    def test_create_actions_failed(self, db_session):
        actions: List[dict] = []
        for _ in range(NUMBER_OF_SEEDS):
            action = {
                "tenant_id": SINGLE_TENANT_UUID,
                "installed_by": "pytest",
                "installation_time": time.time(),
                "name": "test",
                "use": "@test",
                "action_raw": "",
            }
            actions.append(action)
        try:
            ActionsFactory.add_actions(SINGLE_TENANT_UUID, "pytest", actions)
            pytest.fail(
                pytrace=False,
                msg="Adding duplicated actions should throws ActionsFactoryException",
            )
        except ActionsFactoryException:
            pass
    
    @pytest.mark.usefixtures("setup_db")
    def test_remove_action(self, db_session):
        try:
            actions = ActionsFactory.get_all_actions(SINGLE_TENANT_UUID)
            ActionsFactory.remove_action(SINGLE_TENANT_UUID, actions[0].id)
            actions = ActionsFactory.get_all_actions(SINGLE_TENANT_UUID)
            assert len(actions) == 9
        except ActionsFactoryException:
            pytest.fail(pytrace=True, msg="Remove an valid action should not raise ActionsFactoryException")

    @pytest.mark.usefixtures("setup_db")
    def test_remove_action_no_found(self, db_session):
        try:
            removed_action = ActionsFactory.remove_action(SINGLE_TENANT_UUID, "no_found_action")
            assert removed_action is None
        except ActionsFactoryException:
            pytest.fail(pytrace=True, msg="Remove an no-found action should not raise ActionsFactoryException")
     
        
    @pytest.mark.usefixtures("setup_db")
    def test_update_action(self, db_session):
        actions = ActionsFactory.get_all_actions(SINGLE_TENANT_UUID)
        update_action = actions[0]
        try:
            ActionsFactory.update_action(SINGLE_TENANT_UUID, update_action.id, {
                'name': 'test_updated',
                'use': '@test_updated'
            })
            action = ActionsFactory.get_action(SINGLE_TENANT_UUID, update_action.id)
            assert action.name == 'test_updated' and action.use == '@test_updated'
        except ActionsFactoryException:
            pytest.fail(pytrace=True, msg="Update an valid action should not raise ActionsFactoryException")


    @pytest.mark.usefixtures("setup_db")
    def test_update_action_no_found(self, db_session):
        action_id = 'no_found'
        try:
            ActionsFactory.update_action(SINGLE_TENANT_UUID, action_id, {
                'name': 'test_updated',
                'use': '@test_updated'
            })
            pytest.fail(pytrace=True, msg="Update an action that does not exist  in database shoudl raise ActionsFactoryException")
        except ActionsFactoryException:
            pass

class TestActionAPI:
    pass