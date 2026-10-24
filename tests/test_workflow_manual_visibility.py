from datetime import datetime, timezone

import pytest

from keep.api.models.workflow import WorkflowDTO
from keep.functions import cyaml


@pytest.mark.parametrize("visible", [None, True, False])
def test_manual_visibility_is_derived_from_persisted_yaml(visible):
    raw = {
        "id": "automatic-incident-update",
        "triggers": [{"type": "incident", "events": ["created"]}],
        "actions": [],
    }
    if visible is not None:
        raw["manual_visible"] = visible
    workflow = WorkflowDTO(
        id="workflow-id",
        created_by="test@example.com",
        creation_time=datetime.now(timezone.utc),
        providers=[],
        workflow_raw=cyaml.dump(raw),
    )

    assert workflow.dict()["manual_visible"] is (visible is not False)
    assert workflow.disabled is False
    assert workflow.canRun is True
    assert cyaml.safe_load(workflow.workflow_raw) == raw

    # The formatted YAML returned by list/detail APIs retains the setting.
    restored = WorkflowDTO(**workflow.dict())
    assert restored.manual_visible is workflow.manual_visible
