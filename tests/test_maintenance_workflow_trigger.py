import threading
from datetime import datetime
from unittest.mock import Mock

from keep.api.models.db.maintenance_window import MaintenanceWindowDto
from keep.workflowmanager.workflowmanager import (
    WorkflowManager,
    get_maintenance_events,
)


def _maintenance_dto():
    return MaintenanceWindowDto(
        id=1,
        name="db upgrade",
        cel_query="true",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 1, 2),
    )


def _manager_with_workflow(workflow_triggers):
    manager = WorkflowManager.__new__(WorkflowManager)
    manager.logger = Mock()

    workflow_model = Mock(is_disabled=False)
    workflow_model.id = "workflow1"
    manager.workflow_store = Mock()
    manager.workflow_store.get_all_workflows.return_value = [workflow_model]

    workflow = Mock()
    workflow.workflow_triggers = workflow_triggers
    manager._get_workflow_from_store = Mock(return_value=workflow)

    manager.scheduler = Mock()
    manager.scheduler.lock = threading.Lock()
    manager.scheduler.workflows_to_run = []
    return manager


def test_get_maintenance_events_filters_by_type_and_flattens():
    triggers = [
        {"type": "alert", "events": ["created"]},
        {"type": "maintenance", "events": ["created", "deleted"]},
        {"type": "maintenance", "events": ["updated"]},
    ]
    assert get_maintenance_events(triggers) == ["created", "deleted", "updated"]


def test_get_maintenance_events_empty_without_maintenance_trigger():
    triggers = [{"type": "incident", "events": ["created"]}]
    assert get_maintenance_events(triggers) == []


def test_insert_maintenance_enqueues_matching_workflow():
    manager = _manager_with_workflow(
        [{"type": "maintenance", "events": ["created", "deleted"]}]
    )
    dto = _maintenance_dto()

    manager.insert_maintenance("test_tenant", dto, "created")

    assert len(manager.scheduler.workflows_to_run) == 1
    run = manager.scheduler.workflows_to_run[0]
    assert run["triggered_by"] == "maintenance:created"
    assert run["event"] is dto
    assert run["workflow_id"] == "workflow1"
    assert run["tenant_id"] == "test_tenant"


def test_insert_maintenance_skips_when_action_not_subscribed():
    manager = _manager_with_workflow([{"type": "maintenance", "events": ["created"]}])

    manager.insert_maintenance("test_tenant", _maintenance_dto(), "updated")

    assert manager.scheduler.workflows_to_run == []
