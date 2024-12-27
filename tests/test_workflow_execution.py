import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytz

from keep.api.core.db import get_last_workflow_execution_by_workflow_id
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.logging import WorkflowLoggerAdapter
from keep.api.models.alert import AlertDto, AlertStatus, IncidentDto
from keep.api.models.db.workflow import Workflow, WorkflowExecutionLog
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


workflow_definition_with_two_providers = """workflow:
id: susu-and-sons
description: Just to test the logs of 2 providers
triggers:
- type: alert
  filters:
  - key: name
    value: "server-is-hamburger"
steps:
- name: keep_step
  provider:
    type: keep
    with:
      filters:
        - key: status
          value: open
actions:
- name: console_action
  provider:
    type: console
    with:
      message: |
        "Tier 1 Alert: {{ alert.name }} - {{ alert.description }}
        Alert details: {{ alert }}"
"""


@pytest.fixture(scope="module")
def workflow_manager():
    """
    Fixture to create and manage a WorkflowManager instance.
    """
    manager = None
    try:
        from keep.workflowmanager.workflowscheduler import WorkflowScheduler

        scheduler = WorkflowScheduler(None)
        manager = WorkflowManager.get_instance()
        scheduler.workflow_manager = manager
        manager.scheduler = scheduler
        asyncio.run(manager.start())
        yield manager
    finally:
        if manager:
            try:
                manager.stop()
                # Give some time for threads to clean up
                time.sleep(1)
            except Exception as e:
                print(f"Error stopping workflow manager: {e}")


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


@pytest.fixture
def setup_workflow_with_two_providers(db_session):
    """
    Fixture to set up a workflow in the database before each test.
    It creates a Workflow object with the predefined workflow definition and adds it to the database.
    """
    workflow = Workflow(
        id="susu-and-sons",
        name="susu-and-sons",
        tenant_id=SINGLE_TENANT_UUID,
        description="some stuff for unit testing",
        created_by="tal@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_with_two_providers,
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
    while (
        workflow_execution is None
        or workflow_execution.status == "in_progress"
        and count < 30
    ):
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
    while (
        workflow_execution is None
        or workflow_execution.status == "in_progress"
        and count < 30
    ):
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
    while (
        workflow_execution is None
        or workflow_execution.status == "in_progress"
        and count < 30
    ):
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
        (
            enabled_workflow_execution is None
            or enabled_workflow_execution.status == "in_progress"
        )
        and disabled_workflow_execution is None
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


@pytest.mark.timeout(15)
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
        while (
            workflow_execution is None
            or workflow_execution.status == "in_progress"
            and count < 30
        ):
            workflow_execution = get_last_workflow_execution_by_workflow_id(
                SINGLE_TENANT_UUID, workflow_id
            )
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


logs_counter = {}


def count_logs(instance, original_method):
    log_levels = logging.getLevelNamesMapping()

    def wrapper(*args, **kwargs):
        level_name = original_method.__name__.upper()
        max_level = instance.getEffectiveLevel()
        current_level = log_levels[level_name]
        if current_level >= max_level:
            logs_counter.setdefault(instance.workflow_execution_id, defaultdict(int))
            logs_counter[instance.workflow_execution_id]["all"] += 1
            logs_counter[instance.workflow_execution_id][level_name] += 1

        return original_method(*args, **kwargs)

    return wrapper


def fake_workflow_adapter(
    logger, context_manager, tenant_id, workflow_id, workflow_execution_id
):
    adapter = WorkflowLoggerAdapter(
        logger, context_manager, tenant_id, workflow_id, workflow_execution_id
    )

    adapter.info = count_logs(adapter, adapter.info)
    adapter.debug = count_logs(adapter, adapter.debug)
    adapter.warning = count_logs(adapter, adapter.warning)
    adapter.error = count_logs(adapter, adapter.error)
    adapter.critical = count_logs(adapter, adapter.critical)
    return adapter


@pytest.mark.parametrize(
    "test_app, test_case, alert_statuses, expected_tier, db_session",
    [
        ({"AUTH_TYPE": "NOAUTH"}, "No action", [[0, "firing"]], None, None),
    ],
    indirect=["test_app", "db_session"],
)
def test_workflow_execution_logs(
    db_session,
    test_app,
    create_alert,
    setup_workflow_with_two_providers,
    workflow_manager,
    test_case,
    alert_statuses,
    expected_tier,
):
    with patch(
        "keep.contextmanager.contextmanager.WorkflowLoggerAdapter",
        side_effect=fake_workflow_adapter,
    ), patch("keep.api.logging.RUNNING_IN_CLOUD_RUN", value=True):
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
            name="server-is-hamburger",
            status=AlertStatus.FIRING,
            severity="critical",
            fingerprint="fp1",
        )

        # Insert the current alert into the workflow manager
        workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

        # Wait for the workflow execution to complete
        workflow_execution = None
        count = 0
        while (
            workflow_execution is None
            or workflow_execution.status == "in_progress"
            and count < 30
        ):
            workflow_execution = get_last_workflow_execution_by_workflow_id(
                SINGLE_TENANT_UUID, "susu-and-sons"
            )
            time.sleep(1)
            count += 1

        # Check if the workflow execution was successful
        assert workflow_execution is not None
        assert workflow_execution.status == "success"

        logs = (
            db_session.query(WorkflowExecutionLog)
            .filter(WorkflowExecutionLog.workflow_execution_id == workflow_execution.id)
            .all()
        )

        assert len(logs) == logs_counter[workflow_execution.id]["all"]


@pytest.mark.parametrize(
    "test_app, test_case, alert_statuses, expected_tier, db_session",
    [
        ({"AUTH_TYPE": "NOAUTH"}, "No action", [[0, "firing"]], None, None),
    ],
    indirect=["test_app", "db_session"],
)
def test_workflow_execution_logs_log_level_debug_console_provider(
    db_session,
    test_app,
    create_alert,
    setup_workflow_with_two_providers,
    workflow_manager,
    test_case,
    alert_statuses,
    expected_tier,
    monkeypatch,
):

    logs_counts = {}
    logs_level_counts = {}
    for level in ["INFO", "DEBUG"]:
        monkeypatch.setenv("KEEP_CONSOLE_PROVIDER_LOG_LEVEL", level)
        with patch(
            "keep.contextmanager.contextmanager.WorkflowLoggerAdapter",
            side_effect=fake_workflow_adapter,
        ), patch("keep.api.logging.RUNNING_IN_CLOUD_RUN", value=True):
            base_time = datetime.now(tz=pytz.utc)

            # Create alerts with specified statuses and timestamps
            alert_statuses.reverse()
            for time_diff, status in alert_statuses:
                alert_status = (
                    AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
                )
                create_alert(
                    "fp1", alert_status, base_time - timedelta(minutes=time_diff)
                )

            time.sleep(1)
            # Create the current alert
            current_alert = AlertDto(
                id="grafana-1-{}".format(level),
                source=["grafana"],
                name="server-is-hamburger",
                status=AlertStatus.FIRING,
                severity="critical",
                fingerprint="fp1-{}".format(level),
            )

            # Insert the current alert into the workflow manager
            workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

            # Wait for the workflow execution to complete
            workflow_execution = None
            count = 0
            time.sleep(1)
            while (
                workflow_execution is None
                or workflow_execution.status == "in_progress"
                and count < 30
            ):
                workflow_execution = get_last_workflow_execution_by_workflow_id(
                    SINGLE_TENANT_UUID, "susu-and-sons"
                )
                time.sleep(1)
                count += 1

            # Check if the workflow execution was successful
            assert workflow_execution is not None
            assert workflow_execution.status == "success"

            logs_counts[workflow_execution.id] = logs_counter[workflow_execution.id][
                "all"
            ]
            logs_level_counts[level] = logs_counter[workflow_execution.id]["all"]

    for workflow_execution_id in logs_counts:
        logs = (
            db_session.query(WorkflowExecutionLog)
            .filter(WorkflowExecutionLog.workflow_execution_id == workflow_execution_id)
            .all()
        )
        assert logs_counts[workflow_execution_id] == len(logs)

    # SHAHAR: What does it even do?
    # assert logs_level_counts["DEBUG"] > logs_level_counts["INFO"]


# test if/else in workflow definition
workflow_definition_routing = """workflow:
  id: alert-routing-policy
  description: Route alerts based on team and environment conditions
  triggers:
    - type: alert
  actions:
    - name: business-hours-check
      if: "keep.is_business_hours(timezone='America/New_York')"
      # stop the workflow if it's business hours
      continue: false
      provider:
        type: mock
        with:
          message: "Alert during business hours, exiting"

    - name: infra-prod-slack
      if: "'{{ alert.team }}' == 'infra' and '{{ alert.env }}' == 'prod'"
      provider:
        type: console
        with:
          channel: prod-infra-alerts
          message: |
            "Infrastructure Production Alert
            Team: {{ alert.team }}
            Environment: {{ alert.env }}
            Description: {{ alert.description }}"

    - name: http-api-errors-slack
      if: "'{{ alert.monitor_name }}' == 'Http API Errors'"
      provider:
        type: console
        with:
          channel: backend-team-alerts
          message: |
            "HTTP API Error Alert
            Monitor: {{ alert.monitor_name }}
            Description: {{ alert.description }}"
      # exit after sending http api error alert
      continue: false

    - name: backend-staging-pagerduty
      if: "'{{ alert.team }}'== 'backend' and  '{{ alert.env }}' == 'staging'"
      provider:
        type: console
        with:
          severity: low
          message: |
            "Backend Staging Alert
            Team: {{ alert.team }}
            Environment: {{ alert.env }}
            Description: {{ alert.description }}"
      # Exit after sending staging alert
      continue: false
"""


@pytest.mark.parametrize(
    "test_app, test_case, alert_data, expected_results, db_session",
    [
        # Test Case 1: During business hours - should exit immediately
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Business Hours Exit",
            {
                "team": "infra",
                "env": "prod",
                "monitor_name": "CPU High",
                "during_business_hours": True,
            },
            {"business-hours-check": ["Alert during business hours, exiting"]},
            None,
        ),
        # Test Case 2: Infra + Prod alert
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Infra Prod Alert",
            {
                "team": "infra",
                "env": "prod",
                "monitor_name": "CPU High",
                "during_business_hours": False,
            },
            {
                "business-hours-check": [],
                "infra-prod-slack": ["Infrastructure Production Alert"],
                "http-api-errors-slack": [],
                "backend-staging-pagerduty": [],
            },
            None,
        ),
        # Test Case 3: HTTP API Errors (should exit after sending)
        (
            {"AUTH_TYPE": "NOAUTH"},
            "HTTP API Errors",
            {
                "team": "backend",
                "env": "prod",
                "monitor_name": "Http API Errors",
                "during_business_hours": False,
            },
            {
                "business-hours-check": [],
                "infra-prod-slack": [],
                "http-api-errors-slack": ["HTTP API Error Alert"],
                "backend-staging-pagerduty": [],
            },
            None,
        ),
        # Test Case 4: Backend + Staging
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Backend Staging Alert",
            {
                "team": "backend",
                "env": "staging",
                "monitor_name": "CPU High",
                "during_business_hours": False,
            },
            {
                "business-hours-check": [],
                "infra-prod-slack": [],
                "http-api-errors-slack": [],
                "backend-staging-pagerduty": ["Backend Staging Alert"],
            },
            None,
        ),
        # Test Case 5: Infra + Prod + HTTP API Errors (should send both alerts)
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Infra Prod with HTTP API Errors",
            {
                "team": "infra",
                "env": "prod",
                "monitor_name": "Http API Errors",
                "during_business_hours": False,
            },
            {
                "business-hours-check": [],
                "infra-prod-slack": ["Infrastructure Production Alert"],
                "http-api-errors-slack": ["HTTP API Error Alert"],
                "backend-staging-pagerduty": [],
            },
            None,
        ),
        # Test Case 6: Backend + HTTP API Errors + Staging (should only send HTTP API error)
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Backend Staging with HTTP API Errors",
            {
                "team": "backend",
                "env": "staging",
                "monitor_name": "Http API Errors",
                "during_business_hours": False,
            },
            {
                "business-hours-check": [],
                "infra-prod-slack": [],
                "http-api-errors-slack": ["HTTP API Error Alert"],
                "backend-staging-pagerduty": [],
            },
            None,
        ),
    ],
    indirect=["test_app", "db_session"],
)
def test_alert_routing_policy(
    db_session,
    test_app,
    workflow_manager,
    test_case,
    alert_data,
    expected_results,
    mocker,
):
    # Setup the workflow
    workflow = Workflow(
        id="alert-routing-policy",
        name="alert-routing-policy",
        tenant_id=SINGLE_TENANT_UUID,
        description="Route alerts based on team and environment conditions",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_routing,
    )
    db_session.add(workflow)
    db_session.commit()

    # Mock business hours check if needed
    if alert_data.get("during_business_hours"):
        mocker.patch("keep.functions.is_business_hours", return_value=True)
    else:
        mocker.patch("keep.functions.is_business_hours", return_value=False)

    # Create the current alert
    current_alert = AlertDto(
        id="test-alert-1",
        source=["test"],
        name="test-alert",
        status=AlertStatus.FIRING,
        severity="critical",
        team=alert_data["team"],
        env=alert_data["env"],
        monitor_name=alert_data["monitor_name"],
    )

    # Insert the alert into workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    # Wait for workflow execution
    workflow_execution = None
    count = 0
    while (
        workflow_execution is None
        or workflow_execution.status == "in_progress"
        and count < 30
    ):
        workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "alert-routing-policy"
        )
        if workflow_execution is not None and workflow_execution.status == "success":
            break
        time.sleep(1)
        count += 1

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Check if the actions were triggered as expected
    for action_name, expected_messages in expected_results.items():
        if not expected_messages:
            assert workflow_execution.results[action_name] == []
        else:
            for expected_message in expected_messages:
                assert any(
                    # support both list and dict
                    expected_message in json.dumps(result)
                    for result in workflow_execution.results[action_name]
                ), f"Expected message '{expected_message}' not found in {action_name} results"


workflow_definition_nested = """workflow:
  id: nested-conditional-flow
  description: Test nested conditional logic with continue flags
  triggers:
    - type: alert
  actions:
    - name: priority-check
      if: "{{ alert.priority }} == 'p0'"
      continue: false  # Stop if P0 incident
      provider:
        type: console
        with:
          message: "P0 incident detected, bypassing all other checks"

    - name: region-eu-check
      if: "{{ alert.region }} == 'eu'"
      provider:
        type: console
        with:
          message: "EU Region Alert"
      continue: true  # Continue to sub-conditions

    - name: eu-gdpr-check
      if: "{{ alert.region }} == 'eu' and {{ alert.contains_pii }} == 'True'"
      provider:
        type: console
        with:
          message: "GDPR-related incident detected"
      # Stop after GDPR alert
      continue: false

    - name: eu-regular-alert
      if: "{{ alert.region }} == 'eu' and {{ alert.contains_pii }} == 'False'"
      provider:
        type: console
        with:
          message: "Regular EU incident"
      continue: true

    - name: low-priority-check
      if: "{{ alert.priority }} in ['p3', 'p4']"
      provider:
        type: console
        with:
          message: "Low priority incident detected"
"""


@pytest.mark.parametrize(
    "test_app, test_case, alert_data, expected_results, db_session",
    [
        # Test Case 1: P0 incident - should exit immediately
        (
            {"AUTH_TYPE": "NOAUTH"},
            "P0 Priority Exit",
            {"priority": "p0", "region": "eu", "contains_pii": True},
            {
                "priority-check": ["P0 incident detected, bypassing all other checks"],
                "region-eu-check": [],
                "eu-gdpr-check": [],
                "eu-regular-alert": [],
                "low-priority-check": [],
            },
            None,
        ),
        # Test Case 2: EU Region with PII - should stop after GDPR check
        (
            {"AUTH_TYPE": "NOAUTH"},
            "EU PII Alert",
            {"priority": "p2", "region": "eu", "contains_pii": True},
            {
                "priority-check": [],
                "region-eu-check": ["EU Region Alert"],
                "eu-gdpr-check": ["GDPR-related incident detected"],
                "eu-regular-alert": [],
                "low-priority-check": [],
            },
            None,
        ),
        # Test Case 3: EU Region without PII - should continue to low priority check
        (
            {"AUTH_TYPE": "NOAUTH"},
            "EU Regular Alert",
            {"priority": "p3", "region": "eu", "contains_pii": False},
            {
                "priority-check": [],
                "region-eu-check": ["EU Region Alert"],
                "eu-gdpr-check": [],
                "eu-regular-alert": ["Regular EU incident"],
                "low-priority-check": ["Low priority incident detected"],
            },
            None,
        ),
        # Test Case 4: Non-EU P3 alert - should only trigger low priority
        (
            {"AUTH_TYPE": "NOAUTH"},
            "Non-EU Low Priority",
            {"priority": "p3", "region": "us", "contains_pii": False},
            {
                "priority-check": [],
                "region-eu-check": [],
                "eu-gdpr-check": [],
                "eu-regular-alert": [],
                "low-priority-check": ["Low priority incident detected"],
            },
            None,
        ),
    ],
    indirect=["test_app", "db_session"],
)
def test_nested_conditional_flow(
    db_session,
    test_app,
    workflow_manager,
    test_case,
    alert_data,
    expected_results,
    mocker,
):
    # Setup the workflow
    workflow = Workflow(
        id="nested-conditional-flow",
        name="nested-conditional-flow",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test nested conditional logic with continue flags",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_nested,
    )
    db_session.add(workflow)
    db_session.commit()

    # Create the current alert
    current_alert = AlertDto(
        id="test-alert-1",
        source=["test"],
        name="test-alert",
        status=AlertStatus.FIRING,
        severity="critical",
        priority=alert_data["priority"],
        region=alert_data["region"],
        contains_pii=alert_data["contains_pii"],
    )

    # Insert the alert into workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

    # Wait for workflow execution
    workflow_execution = None
    count = 0
    while (
        workflow_execution is None
        or workflow_execution.status == "in_progress"
        and count < 30
    ):
        workflow_execution = get_last_workflow_execution_by_workflow_id(
            SINGLE_TENANT_UUID, "nested-conditional-flow"
        )
        if workflow_execution is not None and workflow_execution.status == "success":
            break

        elif workflow_execution is not None and workflow_execution.status == "error":
            raise Exception("Workflow execution failed")

        time.sleep(1)
        count += 1

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Check if the actions were triggered as expected
    for action_name, expected_messages in expected_results.items():
        if not expected_messages:
            assert workflow_execution.results[action_name] == []
        else:
            for expected_message in expected_messages:
                assert any(
                    expected_message in json.dumps(result)
                    for result in workflow_execution.results[action_name]
                ), f"Expected message '{expected_message}' not found in {action_name} results"
