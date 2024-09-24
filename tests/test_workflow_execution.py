import asyncio
import time
from datetime import datetime, timedelta

import pytest
import pytz

from keep.api.core.db import get_last_workflow_execution_by_workflow_id
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus, IncidentDto
from keep.api.models.db.workflow import Workflow
from keep.workflowmanager.workflowmanager import WorkflowManager
from tests.fixtures.client import client, test_app  # noqa

# This workflow definition is used to test the execution of workflows based on alert firing times.
# It defines two actions:
# 1. send-slack-message-tier-1: Triggered when an alert has been firing for more than 15 minutes but less than 30 minutes.
# 2. send-slack-message-tier-2: Triggered when an alert has been firing for more than 30 minutes.
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
    """
    Fixture to create and manage a WorkflowManager instance for the duration of the module.
    It starts the manager asynchronously and stops it after all tests are completed.
    """
    manager = WorkflowManager.get_instance()
    asyncio.run(manager.start())
    while not manager.started:
        time.sleep(0.1)
    yield manager
    manager.stop()


@pytest.fixture
def setup_workflow(db_session):
    """
    Fixture to set up a workflow in the database before each test.
    It creates a Workflow object with the predefined workflow definition and adds it to the database.
    """
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
    "test_app, test_case, alert_statuses, expected_tier, db_session",
    [
        ({"AUTH_TYPE": "NOAUTH"}, "No action", [[0, "firing"]], None, None),
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 1", [[20, "firing"]], 1, None),
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 2", [[35, "firing"]], 2, None),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved before tier 1",
            [[10, "firing"], [11, "resolved"]],
            None,
            None,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved after tier 1",
            [[20, "firing"], [25, "resolved"]],
            1,
            None,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved after tier 2",
            [[35, "firing"], [40, "resolved"]],
            2,
            None,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Multiple firings, last one tier 2",
            [[10, "firing"], [20, "firing"], [35, "firing"]],
            2,
            None,
        ),
        ({"AUTH_TYPE": "NOAUTH"}, "No action", [[0, "firing"]], None, {"db": "mysql"}),
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 1", [[20, "firing"]], 1, {"db": "mysql"}),
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 2", [[35, "firing"]], 2, {"db": "mysql"}),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved before tier 1",
            [[10, "firing"], [11, "resolved"]],
            None,
            {"db": "mysql"},
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved after tier 1",
            [[20, "firing"], [25, "resolved"]],
            1,
            {"db": "mysql"},
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved after tier 2",
            [[35, "firing"], [40, "resolved"]],
            2,
            {"db": "mysql"},
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Multiple firings, last one tier 2",
            [[10, "firing"], [20, "firing"], [35, "firing"]],
            2,
            {"db": "mysql"},
        ),
    ],
    indirect=["test_app", "db_session"],
)
def test_workflow_execution(
    db_session,
    test_app,
    create_alert,
    setup_workflow,
    workflow_manager,
    test_case,
    alert_statuses,
    expected_tier,
):
    """
    This test function verifies the execution of the workflow based on different alert scenarios.
    It uses parameterized testing to cover various cases of alert firing and resolution times.
    It now also tests with both SQLite (default) and MySQL databases.

    The test does the following:
    1. Creates alerts with specified statuses and timestamps.
    2. Inserts a current alert into the workflow manager.
    3. Waits for the workflow execution to complete.
    4. Checks if the workflow execution was successful.
    5. Verifies if the correct tier action was triggered based on the alert firing time.

    Parameters:
    - test_case: Description of the test scenario.
    - alert_statuses: List of [time_diff, status] pairs representing alert history.
    - expected_tier: The expected tier (1, 2, or None) that should be triggered.

    The test covers scenarios such as:
    - Alerts that don't trigger any action
    - Alerts that trigger Tier 1 (15-30 minutes of firing)
    - Alerts that trigger Tier 2 (>30 minutes of firing)
    - Alerts that are resolved before or after reaching different tiers
    - Multiple firing alerts with the last one determining the tier
    """
    base_time = datetime.now(tz=pytz.utc)

    # Create alerts with specified statuses and timestamps
    alert_statuses.reverse()
    for time_diff, status in alert_statuses:
        alert_status = (
            AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
        )
        create_alert("fp1", alert_status, base_time - timedelta(minutes=time_diff))

    time.sleep(1)
    # Create the current alert
    current_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-down",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    # Insert the current alert into the workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    # Wait for the workflow execution to complete
    workflow_execution = None
    count = 0
    status = None
    while workflow_execution is None and count < 30 and status != "success":
        workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "alert-time-check"
        )
        if workflow_execution is not None:
            status = workflow_execution.status
        time.sleep(1)
        count += 1

    # Check if the workflow execution was successful
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Verify if the correct tier action was triggered
    if expected_tier is None:
        assert workflow_execution.results["send-slack-message-tier-1"] == []
        assert workflow_execution.results["send-slack-message-tier-2"] == []
    elif expected_tier == 1:
        assert workflow_execution.results["send-slack-message-tier-2"] == []
        assert "Tier 1" in workflow_execution.results["send-slack-message-tier-1"][0]
    elif expected_tier == 2:
        assert workflow_execution.results["send-slack-message-tier-1"] == []
        assert "Tier 2" in workflow_execution.results["send-slack-message-tier-2"][0]


workflow_definition2 = """workflow:
id: %s
description: send slack message only the first time an alert fires
triggers:
  - type: alert
    filters:
      - key: name
        value: "server-is-down"
actions:
  - name: send-slack-message
    if: "keep.is_first_time('{{ alert.fingerprint }}', '24h')"
    provider:
      type: console
      with:
        message: |
          "Tier 1 Alert: {{ alert.name }} - {{ alert.description }}
          Alert details: {{ alert }}"
"""


@pytest.mark.parametrize(
    "test_app, workflow_id, test_case, alert_statuses, expected_action",
    [
        (
            {"AUTH_TYPE": "NOAUTH"},
            "alert-first-firing",
            "First firing",
            [[0, "firing"]],
            True,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "alert-second-firing",
            "Second firing within 24h",
            [[0, "firing"], [1, "firing"]],
            False,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "firing-resolved-firing-24",
            "First firing, resolved, and fired again after 24h",
            [[0, "firing"], [1, "resolved"], [25, "firing"]],
            True,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "multiple-firings-24",
            "Multiple firings within 24h",
            [[0, "firing"], [1, "firing"], [2, "firing"], [3, "firing"]],
            False,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "resolved-fired-24",
            "Resolved and fired again within 24h",
            [[0, "firing"], [1, "resolved"], [2, "firing"]],
            False,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "first-firing-multiple-resolutions",
            "First firing after multiple resolutions",
            [[0, "resolved"], [1, "resolved"], [2, "firing"]],
            True,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "firing-exactly-24",
            "Firing exactly at 24h boundary",
            [[0, "firing"], [24, "firing"]],
            True,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "complex-scenario",
            "Complex scenario with multiple status changes",
            [
                [0, "firing"],
                [1, "resolved"],
                [2, "firing"],
                [3, "resolved"],
                [26, "firing"],
            ],
            False,
        ),
    ],
    indirect=["test_app"],
)
def test_workflow_execution_2(
    db_session,
    test_app,
    create_alert,
    workflow_manager,
    workflow_id,
    test_case,
    alert_statuses,
    expected_action,
):
    """
    This test function verifies the execution of the workflow based on different alert scenarios.
    It uses parameterized testing to cover various cases of alert firing and resolution times.

    The test does the following:
    1. Creates alerts with specified statuses and timestamps.
    2. Inserts a current alert into the workflow manager.
    3. Waits for the workflow execution to complete.
    4. Checks if the workflow execution was successful.
    5. Verifies if the correct action was triggered based on the alert firing time.

    Parameters:
    - test_case: Description of the test scenario.
    - alert_statuses: List of [time_diff, status] pairs representing alert history.
    - expected_action: Boolean indicating if the action is expected to be triggered.

    The test covers scenarios such as:
    - First firing of an alert
    - Second firing of an alert within 24 hours
    - Firing of an alert after resolving and firing again after 24 hours
    """
    workflow = Workflow(
        id=workflow_id,
        name=workflow_id,
        tenant_id=SINGLE_TENANT_UUID,
        description="Send slack message only the first time an alert fires",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition2 % workflow_id,
    )
    db_session.add(workflow)
    db_session.commit()
    base_time = datetime.now(tz=pytz.utc)

    # Create alerts with specified statuses and timestamps
    for time_diff, status in alert_statuses:
        alert_status = (
            AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
        )
        create_alert("fp1", alert_status, base_time - timedelta(hours=time_diff))

    # Create the current alert
    current_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-down",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    # Insert the current alert into the workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Wait for the workflow execution to complete
    workflow_execution = None
    count = 0
    status = None
    while workflow_execution is None and count < 30 and status != "success":
        workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID,
            workflow_id,
        )
        if workflow_execution is not None:
            status = workflow_execution.status
        time.sleep(1)
        count += 1

    assert len(workflow_manager.scheduler.workflows_to_run) == 0
    # Check if the workflow execution was successful
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Verify if the correct action was triggered
    if expected_action:
        assert "Tier 1 Alert" in workflow_execution.results["send-slack-message"][0]
    else:
        assert workflow_execution.results["send-slack-message"] == []


workflow_definition_3 = """workflow:
id: alert-time-check
description: Handle alerts based on startedAt timestamp
triggers:
- type: alert
  filters:
  - key: name
    value: "server-is-down"
actions:
- name: send-slack-message-tier-0
  if: keep.get_firing_time('{{ alert }}', 'minutes') > 0 and keep.get_firing_time('{{ alert }}', 'minutes') < 10
  provider:
    type: console
    with:
      message: |
        "Tier 0 Alert: {{ alert.name }} - {{ alert.description }}
        Alert details: {{ alert }}"
- name: send-slack-message-tier-1
  if: "keep.get_firing_time('{{ alert }}', 'minutes') >= 10 and keep.get_firing_time('{{ alert }}', 'minutes') < 30"
  provider:
    type: console
    with:
      message: |
        "Tier 1 Alert: {{ alert.name }} - {{ alert.description }}
         Alert details: {{ alert }}"
"""


@pytest.mark.parametrize(
    "test_app, test_case, alert_statuses, expected_tier, db_session",
    [
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 0", [[0, "firing"]], 0, None),
        ({"AUTH_TYPE": "NOAUTH"}, "Tier 1", [[10, "firing"], [0, "firing"]], 1, None),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Resolved",
            [[15, "firing"], [5, "firing"], [0, "resolved"]],
            None,
            None,
        ),
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Tier 0 again",
            [[20, "firing"], [10, "firing"], [5, "resolved"], [0, "firing"]],
            0,
            None,
        ),
    ],
    indirect=["test_app", "db_session"],
)
def test_workflow_execution3(
    db_session,
    test_app,
    create_alert,
    workflow_manager,
    test_case,
    alert_statuses,
    expected_tier,
):
    workflow = Workflow(
        id="alert-first-time",
        name="alert-first-time",
        tenant_id=SINGLE_TENANT_UUID,
        description="Send slack message only the first time an alert fires",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_3,
    )
    db_session.add(workflow)
    db_session.commit()
    base_time = datetime.now(tz=pytz.utc)

    # Create alerts with specified statuses and timestamps
    for time_diff, status in alert_statuses:
        alert_status = (
            AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
        )
        create_alert("fp1", alert_status, base_time - timedelta(minutes=time_diff))

    # Create the current alert
    current_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-down",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    # sleep one second to avoid the case where tier0 alerts are not triggered
    time.sleep(1)

    # Insert the current alert into the workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    # Wait for the workflow execution to complete
    workflow_execution = None
    count = 0
    status = None
    while workflow_execution is None and count < 30 and status != "success":
        workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "alert-first-time"
        )
        if workflow_execution is not None:
            status = workflow_execution.status
        time.sleep(1)
        count += 1

    # Check if the workflow execution was successful

    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Verify if the correct tier action was triggered
    if expected_tier is None:
        assert workflow_execution.results["send-slack-message-tier-0"] == []
        assert workflow_execution.results["send-slack-message-tier-1"] == []
    elif expected_tier == 0:
        assert workflow_execution.results["send-slack-message-tier-1"] == []
        assert "Tier 0" in workflow_execution.results["send-slack-message-tier-0"][0]
    elif expected_tier == 1:
        assert workflow_execution.results["send-slack-message-tier-0"] == []
        assert "Tier 1" in workflow_execution.results["send-slack-message-tier-1"][0]


workflow_definition_for_enabled_disabled = """workflow:
id: %s
description: Handle alerts based on startedAt timestamp
triggers:
- type: alert
  filters:
  - key: name
    value: "server-is-down"
actions:
- name: send-slack-message-tier-0
  if: keep.get_firing_time('{{ alert }}', 'minutes') > 0 and keep.get_firing_time('{{ alert }}', 'minutes') < 10
  provider:
    type: console
    with:
      message: |
        "Tier 0 Alert: {{ alert.name }} - {{ alert.description }}
        Alert details: {{ alert }}"
- name: send-slack-message-tier-1
  if: "keep.get_firing_time('{{ alert }}', 'minutes') >= 10 and keep.get_firing_time('{{ alert }}', 'minutes') < 30"
  provider:
    type: console
    with:
      message: |
        "Tier 1 Alert: {{ alert.name }} - {{ alert.description }}
         Alert details: {{ alert }}"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        ({"AUTH_TYPE": "NOAUTH"}),
    ],
    indirect=["test_app"],
)
def test_workflow_execution_with_disabled_workflow(
    db_session,
    test_app,
    create_alert,
    workflow_manager,
):
    enabled_id = "enabled-workflow"
    enabled_workflow = Workflow(
        id=enabled_id,
        name="enabled-workflow",
        tenant_id=SINGLE_TENANT_UUID,
        description="This workflow is enabled and should be executed",
        created_by="test@keephq.dev",
        interval=0,
        is_disabled=False,
        workflow_raw=workflow_definition_for_enabled_disabled % enabled_id,
    )

    disabled_id = "disabled-workflow"
    disabled_workflow = Workflow(
        id=disabled_id,
        name="disabled-workflow",
        tenant_id=SINGLE_TENANT_UUID,
        description="This workflow is disabled and should not be executed",
        created_by="test@keephq.dev",
        interval=0,
        is_disabled=True,
        workflow_raw=workflow_definition_for_enabled_disabled % disabled_id,
    )

    db_session.add(enabled_workflow)
    db_session.add(disabled_workflow)
    db_session.commit()

    base_time = datetime.now(tz=pytz.utc)

    create_alert("fp1", AlertStatus.FIRING, base_time)
    current_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-down",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    # Sleep one second to avoid the case where tier0 alerts are not triggered
    time.sleep(1)

    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    enabled_workflow_execution = None
    disabled_workflow_execution = None
    count = 0

    while (
        enabled_workflow_execution is None and disabled_workflow_execution is None
    ) and count < 30:
        enabled_workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, enabled_id
        )
        disabled_workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, disabled_id
        )

        time.sleep(1)
        count += 1

    assert enabled_workflow_execution is not None
    assert enabled_workflow_execution.status == "success"

    assert disabled_workflow_execution is None


workflow_definition_4 = """workflow:
id: incident-triggers-test-created-updated
description: test incident triggers
triggers:
- type: incident
  events:
  - updated
  - created
name: created-updated
owners: []
services: []
steps: []
actions:
- name: mock-action
  provider:
    type: console
    with:
      message: |
        "incident: {{ incident.name }}"
"""

workflow_definition_5 = """workflow:
id: incident-incident-triggers-test-deleted
description: test incident triggers
triggers:
- type: incident
  events:
  - deleted
name: deleted
owners: []
services: []
steps: []
actions:
- name: mock-action
  provider:
    type: console
    with:
      message: |
        "deleted incident: {{ incident.name }}"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        ({"AUTH_TYPE": "NOAUTH"}),
    ],
    indirect=["test_app"],
)
def test_workflow_incident_triggers(
    db_session,
    test_app,
    workflow_manager,
):
    workflow_created = Workflow(
        id="incident-triggers-test-created-updated",
        name="incident-triggers-test-created-updated",
        tenant_id=SINGLE_TENANT_UUID,
        description="Check that incident triggers works",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_4,
    )
    db_session.add(workflow_created)
    db_session.commit()

    # Create the current alert
    incident = IncidentDto(
        id="ba9ddbb9-3a83-40fc-9ace-1e026e08ca2b",
        user_generated_name="incident",
        alerts_count=0,
        alert_sources=[],
        services=[],
        severity="critical",
        is_predicted=False,
        is_confirmed=True,
    )

    # Insert the current alert into the workflow manager

    def wait_workflow_execution(workflow_id):
        # Wait for the workflow execution to complete
        workflow_execution = None
        count = 0
        status = None
        while workflow_execution is None and count < 30 and status != "success":
            workflow_execution = get_last_workflow_execution_by_workflow_id(
                SINGLE_TENANT_UUID, workflow_id
            )
            if workflow_execution is not None:
                status = workflow_execution.status
            time.sleep(1)
            count += 1
        return workflow_execution

    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "created")
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    workflow_execution_created = wait_workflow_execution(
        "incident-triggers-test-created-updated"
    )
    assert workflow_execution_created is not None
    assert workflow_execution_created.status == "success"
    assert workflow_execution_created.results["mock-action"] == [
        '"incident: incident"\n'
    ]
    assert len(workflow_manager.scheduler.workflows_to_run) == 0

    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "updated")
    assert len(workflow_manager.scheduler.workflows_to_run) == 1
    workflow_execution_updated = wait_workflow_execution(
        "incident-triggers-test-created-updated"
    )
    assert workflow_execution_updated is not None
    assert workflow_execution_updated.status == "success"
    assert workflow_execution_updated.results["mock-action"] == [
        '"incident: incident"\n'
    ]

    # incident-triggers-test-created-updated should not be triggered
    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "deleted")
    assert len(workflow_manager.scheduler.workflows_to_run) == 0

    workflow_deleted = Workflow(
        id="incident-triggers-test-deleted",
        name="incident-triggers-test-deleted",
        tenant_id=SINGLE_TENANT_UUID,
        description="Check that incident triggers works",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_5,
    )
    db_session.add(workflow_deleted)
    db_session.commit()

    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "deleted")
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # incident-triggers-test-deleted should be triggered now
    workflow_execution_deleted = wait_workflow_execution(
        "incident-triggers-test-deleted"
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 0

    assert workflow_execution_deleted is not None
    assert workflow_execution_deleted.status == "success"
    assert workflow_execution_deleted.results["mock-action"] == [
        '"deleted incident: incident"\n'
    ]
