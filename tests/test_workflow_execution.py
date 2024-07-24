import asyncio
import time
from datetime import datetime, timedelta

import pytest
import pytz

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.workflowmanager.workflowmanager import WorkflowManager

workflow_definition = """workflow:
id: alert-time-check
description: Handle alerts based on startedAt timestamp
triggers:
- type: alert
  filters:
  - key: name
    value: "server-is-down"
actions:
- name: send-slack-message-tier-1
  if: "keep.get_firing_time('{{ alert }}', 'minutes') > 15  and keep.get_firing_time('{{ alert }}', 'minutes') < 30"
  provider:
    type: console
    with:
      message: |
        "Tier 1 Alert: {{ alert.name }} - {{ alert.description }}
        Alert details: {{ alert }}"
- name: send-slack-message-tier-2
  if: "keep.get_firing_time('{{ alert }}', 'minutes') > 30"
  provider:
    type: console
    with:
      message: |
        "Tier 2 Alert: {{ alert.name }} - {{ alert.description }}
         Alert details: {{ alert }}"
"""


@pytest.fixture(scope="module")
def workflow_manager():
    manager = WorkflowManager.get_instance()
    asyncio.run(manager.start())
    while not manager.started:
        time.sleep(0.1)
    yield manager
    manager.stop()


@pytest.fixture
def setup_workflow(db_session):
    workflow = Workflow(
        id="alert-time-check",
        name="alert-time-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts based on startedAt timestamp",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    db_session.add(workflow)
    db_session.commit()


@pytest.mark.parametrize(
    "test_case, alert_statuses, expected_tier",
    [
        ("No action", [[0, "firing"]], None),
        ("Tier 1", [[20, "firing"]], 1),
        ("Tier 2", [[35, "firing"]], 2),
        ("Resolved before tier 1", [[10, "firing"], [11, "resolved"]], None),
        ("Resolved after tier 1", [[20, "firing"], [25, "resolved"]], 1),
        ("Resolved after tier 2", [[35, "firing"], [40, "resolved"]], 2),
        (
            "Multiple firings, last one tier 2",
            [[10, "firing"], [20, "firing"], [35, "firing"]],
            2,
        ),
    ],
)
def test_workflow_execution(
    db_session,
    create_alert,
    setup_workflow,
    workflow_manager,
    test_case,
    alert_statuses,
    expected_tier,
):
    base_time = datetime.now(tz=pytz.utc)

    for time_diff, status in alert_statuses:
        alert_status = (
            AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
        )
        create_alert("fp1", alert_status, base_time - timedelta(minutes=time_diff))

    current_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-down",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    workflow_execution = None
    count = 0
    status = None
    while workflow_execution is None and count < 100 and status != "success":
        workflow_execution = (
            db_session.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == "alert-time-check",
            )
            .first()
        )
        if workflow_execution is not None:
            status = workflow_execution.status
        time.sleep(1)
        count += 1

    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    if expected_tier is None:
        assert workflow_execution.results["send-slack-message-tier-1"] == []
        assert workflow_execution.results["send-slack-message-tier-2"] == []
    elif expected_tier == 1:
        assert workflow_execution.results["send-slack-message-tier-2"] == []
        assert "Tier 1" in workflow_execution.results["send-slack-message-tier-1"][0]
    elif expected_tier == 2:
        assert workflow_execution.results["send-slack-message-tier-1"] == []
        assert "Tier 2" in workflow_execution.results["send-slack-message-tier-2"][0]
