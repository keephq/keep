import asyncio
import json
import time
from datetime import datetime, timedelta

import pytest
import pytz
from fastapi import HTTPException

from keep.api.core.db import (
    assign_alert_to_incident,
    create_incident_from_dict,
    get_all_provisioned_workflows,
    get_last_alerts,
    get_last_workflow_execution_by_workflow_id,
    get_workflow_execution,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.incident import Incident, IncidentStatus
from keep.api.models.db.workflow import Workflow, WorkflowExecution
from keep.api.models.incident import IncidentDto
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identity_managers.db.db_authverifier import (  # noqa
    DbAuthVerifier,
)
from keep.workflowmanager.workflowmanager import WorkflowManager
from tests.fixtures.client import client, test_app  # noqa
from keep.workflowmanager.workflowstore import WorkflowStore

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
      if: "1 == 1"
      for: 1s
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

MAX_WAIT_COUNT = 30


def wait_for_workflow_execution(tenant_id, workflow_id, exclude_ids=None):
    # Wait for the workflow execution to complete
    workflow_execution = None
    count = 0
    while (
        workflow_execution is None or workflow_execution.status == "in_progress"
    ) and count < MAX_WAIT_COUNT:
        try:
            workflow_execution = get_last_workflow_execution_by_workflow_id(
                tenant_id, workflow_id, exclude_ids=exclude_ids
            )
        except Exception as e:
            print(
                f"DEBUG: Poll attempt {count}: execution_id={workflow_execution.id if workflow_execution else None}, "
                f"status={workflow_execution.status if workflow_execution else None}, "
                f"error={e}"
            )
        finally:
            time.sleep(1)
            count += 1
    return workflow_execution


@pytest.fixture
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
    except Exception:
        pass
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
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "alert-time-check"
    )

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
    workflow_execution = wait_for_workflow_execution(SINGLE_TENANT_UUID, workflow_id)

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
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "alert-first-time"
    )

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
    ) and count < MAX_WAIT_COUNT:
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
        is_candidate=False,
    )

    # Insert the current alert into the workflow manager

    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "created")
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    workflow_execution_created = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "incident-triggers-test-created-updated"
    )
    assert workflow_execution_created is not None
    assert workflow_execution_created.status == "success"
    assert workflow_execution_created.results["mock-action"] == [
        '"incident: incident"\n'
    ]
    assert len(workflow_manager.scheduler.workflows_to_run) == 0

    workflow_manager.insert_incident(SINGLE_TENANT_UUID, incident, "updated")
    assert len(workflow_manager.scheduler.workflows_to_run) == 1
    workflow_execution_updated = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "incident-triggers-test-created-updated"
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
    workflow_execution_deleted = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "incident-triggers-test-deleted"
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 0

    assert workflow_execution_deleted is not None
    assert workflow_execution_deleted.status == "success"
    assert workflow_execution_deleted.results["mock-action"] == [
        '"deleted incident: incident"\n'
    ]


# @pytest.mark.parametrize(
#     "test_app, test_case, alert_statuses, expected_tier, db_session",
#     [
#         ({"AUTH_TYPE": "NOAUTH"}, "No action", [[0, "firing"]], None, None),
#     ],
#     indirect=["test_app", "db_session"],
# )
# def test_workflow_execution_logs(
#     db_session,
#     test_app,
#     create_alert,
#     setup_workflow_with_two_providers,
#     workflow_manager,
#     test_case,
#     alert_statuses,
#     expected_tier,
# ):
#     """Test that workflow execution logs are properly stored using WorkflowDBHandler"""
#     base_time = datetime.now(tz=pytz.utc)

#     # Create alerts with specified statuses and timestamps
#     alert_statuses.reverse()
#     for time_diff, status in alert_statuses:
#         alert_status = (
#             AlertStatus.FIRING if status == "firing" else AlertStatus.RESOLVED
#         )
#         create_alert("fp1", alert_status, base_time - timedelta(minutes=time_diff))

#     time.sleep(1)

#     # Create the current alert
#     current_alert = AlertDto(
#         id="grafana-1",
#         source=["grafana"],
#         name="server-is-hamburger",
#         status=AlertStatus.FIRING,
#         severity="critical",
#         fingerprint="fp1",
#     )

#     # Insert the current alert into the workflow manager
#     workflow_manager.insert_events(SINGLE_TENANT_UUID, [current_alert])

#     # Wait for the workflow execution to complete
#     workflow_execution = None
#     count = 0
#     while (
#         workflow_execution is None
#         or workflow_execution.status == "in_progress"
#         and count < 30
#     ):
#         workflow_execution = get_last_workflow_execution_by_workflow_id(
#             SINGLE_TENANT_UUID, "susu-and-sons"
#         )
#         time.sleep(1)
#         count += 1

#     # Check if the workflow execution was successful
#     assert workflow_execution is not None
#     assert workflow_execution.status == "success"

#     # Get logs from DB
#     db_session.expire_all()
#     logs = (
#         db_session.query(WorkflowExecutionLog)
#         .filter(WorkflowExecutionLog.workflow_execution_id == workflow_execution.id)
#         .all()
#     )

#     # Since we're using a filter now, verify that all logs have workflow_execution_id
#     assert len(logs) > 0  # We should have some logs
#     for log in logs:
#         assert log.workflow_execution_id == workflow_execution.id


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
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "alert-routing-policy"
    )

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
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "nested-conditional-flow"
    )

    if workflow_execution is not None and workflow_execution.status == "error":
        raise Exception("Workflow execution failed")

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


workflow_resolve_definition = """workflow:
  id: Resolve-Alert
  name: Resolve Alert
  description: ""
  disabled: false
  triggers:
    - type: alert
  consts: {}
  owners: []
  services: []
  steps: []
  actions:
    - name: resolve-alert
      provider:
        type: mock
        with:
          enrich_alert:
            - key: status
              value: resolved
"""


def test_alert_resolved(db_session, create_alert, workflow_manager):

    # Create the current alert
    create_alert("fp1", AlertStatus.FIRING, datetime.now(tz=pytz.utc), {})

    incident = create_incident_from_dict(
        "keep", {"user_generated_name": "test", "description": "test"}
    )

    assign_alert_to_incident("fp1", incident, SINGLE_TENANT_UUID, db_session)

    # Setup the workflow
    workflow = Workflow(
        id="Resolve-Alert",
        name="Resolve-Alert",
        tenant_id=SINGLE_TENANT_UUID,
        description="Resolve Alert",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_resolve_definition,
    )
    db_session.add(workflow)
    db_session.commit()

    alerts = get_last_alerts(SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)

    assert len(alerts_dto) == 1
    assert alerts_dto[0].status == AlertStatus.FIRING.value

    incident = db_session.query(Incident).first()
    assert incident.status == IncidentStatus.FIRING.value

    # Insert the alert into workflow manager
    workflow_manager.insert_events(SINGLE_TENANT_UUID, alerts_dto)

    # Wait for workflow execution
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "Resolve-Alert"
    )

    if workflow_execution is not None and workflow_execution.status == "error":
        raise Exception("Workflow execution failed")

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    db_session.expire_all()

    alerts = get_last_alerts(SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 1
    assert alerts_dto[0].status == AlertStatus.RESOLVED.value

    incident = db_session.query(Incident).first()
    assert incident.status == IncidentStatus.RESOLVED.value


workflow_definition_with_permissions = """workflow:
  id: workflow-with-permissions
  name: Workflow With Permissions
  description: "A workflow with restricted access"
  permissions:
    - admin
    - noc
    - test@keephq.dev
  triggers:
    - type: manual
  steps: []
  actions:
    - name: console-action
      provider:
        type: console
        with:
          message: "Executed restricted workflow"
"""

workflow_definition_without_permissions = """workflow:
  id: workflow-without-permissions
  name: Workflow Without Permissions
  description: "A workflow without restricted access"
  triggers:
    - type: manual
  steps: []
  actions:
    - name: console-action
      provider:
        type: console
        with:
          message: "Executed unrestricted workflow"
"""


@pytest.mark.parametrize(
    "test_app, token, workflow_id, expected_status",
    [
        # Admin can always run workflows regardless of permissions
        ({"AUTH_TYPE": "DB"}, "admin_token", "workflow-with-permissions", 200),
        # User with role in permissions can run the workflow
        ({"AUTH_TYPE": "DB"}, "noc_token", "workflow-with-permissions", 200),
        # User with email in permissions can run the workflow
        ({"AUTH_TYPE": "DB"}, "listed_email_token", "workflow-with-permissions", 403),
        # User without proper role or email gets forbidden
        ({"AUTH_TYPE": "DB"}, "unlisted_token", "workflow-with-permissions", 403),
        # Anyone can run workflows without permissions
        ({"AUTH_TYPE": "DB"}, "unlisted_token", "workflow-without-permissions", 200),
    ],
    indirect=["test_app"],
)
def test_workflow_permissions(
    db_session,
    test_app,
    client,
    token,
    workflow_id,
    expected_status,
    mocker,
):
    """Test that workflow permissions are enforced correctly when executing workflows."""

    # Setup workflows with and without permissions
    workflow_with_permissions = Workflow(
        id="workflow-with-permissions",
        name="workflow-with-permissions",
        tenant_id=SINGLE_TENANT_UUID,
        description="A workflow with restricted access",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_with_permissions,
    )

    workflow_without_permissions = Workflow(
        id="workflow-without-permissions",
        name="workflow-without-permissions",
        tenant_id=SINGLE_TENANT_UUID,
        description="A workflow without restricted access",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition_without_permissions,
    )

    db_session.add(workflow_with_permissions)
    db_session.add(workflow_without_permissions)
    db_session.commit()
    db_session.refresh(workflow_with_permissions)
    db_session.refresh(workflow_without_permissions)

    # Define user data for different tokens
    user_data = {
        "admin_token": AuthenticatedEntity(
            SINGLE_TENANT_UUID, "admin@keephq.dev", None, "admin"
        ),
        "noc_token": AuthenticatedEntity(
            SINGLE_TENANT_UUID, "noc@keephq.dev", None, "noc"
        ),
        "listed_email_token": AuthenticatedEntity(
            SINGLE_TENANT_UUID, "test@keephq.dev", None, "webhook"
        ),
        "unlisted_token": AuthenticatedEntity(
            SINGLE_TENANT_UUID, "dev@keephq.dev", None, "workflowrunner"
        ),
    }

    # Create a mock function that matches the signature of _verify_bearer_token
    def mock_verify_bearer_token(token, *args, **kwargs):
        if token not in user_data:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_data[token]

    # Mock the DbAuthVerifier._verify_bearer_token method
    mocker.patch(
        "keep.identitymanager.identity_managers.db.db_authverifier.DbAuthVerifier._verify_bearer_token",
        side_effect=mock_verify_bearer_token,
    )

    # Mock the workflow execution process
    mock_wf_manager = mocker.MagicMock()
    mock_scheduler = mocker.MagicMock()
    mock_wf_manager.scheduler = mock_scheduler
    mock_scheduler.handle_manual_event_workflow.return_value = "mock-execution-id"

    # Patch the WorkflowManager.get_instance method
    mocker.patch(
        "keep.workflowmanager.workflowmanager.WorkflowManager.get_instance",
        return_value=mock_wf_manager,
    )

    # Run the workflow manually with the appropriate token
    response = client.post(
        f"/workflows/{workflow_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    # Verify the response status code matches expectations
    assert response.status_code == expected_status

    # If the response should be successful, verify that the workflow execution was attempted
    if expected_status == 200:
        mock_scheduler.handle_manual_event_workflow.assert_called_once()
    else:
        # For 403 responses, the workflow execution should not be attempted
        mock_scheduler.handle_manual_event_workflow.assert_not_called()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_WORKFLOWS_DIRECTORY": "./tests/provision/workflows_4",
        },
    ],
    indirect=True,
)
def test_workflow_executions_after_reprovisioning(
    db_session,
    test_app,
    workflow_manager,
    create_alert,
):
    """Test that workflow executions remain attached to workflows after reprovisioning."""
    # First provision the workflows
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after first provisioning
    first_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(first_provisioned) == 1  # There is 1 workflow in workflows_3 directory

    # Create and execute an alert to trigger the workflow
    first_alert = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="server-is-under-the-weather",
        message="Grafana is under the weather",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp1",
    )

    # Insert the alert into workflow manager to trigger execution
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [first_alert])

    # Wait for workflow execution to complete
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, first_provisioned[0].id
    )

    # Verify first execution was successful
    assert workflow_execution is not None
    assert workflow_execution.status == "success"
    first_execution_id = workflow_execution.id

    # Reprovision the workflows
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after second provisioning
    second_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(second_provisioned) == 1  # Should still be 1 workflow
    assert second_provisioned[0].id == first_provisioned[0].id

    # Verify the workflow execution is still attached
    workflow_execution = get_workflow_execution(SINGLE_TENANT_UUID, first_execution_id)
    assert workflow_execution is not None
    assert workflow_execution.id == first_execution_id
    assert workflow_execution.workflow_id == second_provisioned[0].id

    # Execute another alert to verify the workflow still works
    second_alert = AlertDto(
        id="grafana-2",
        source=["grafana"],
        name="server-is-under-the-weather",
        message="Grafana is under the weather again",
        status=AlertStatus.FIRING,
        severity="critical",
        fingerprint="fp2",
    )

    workflow_manager.insert_events(SINGLE_TENANT_UUID, [second_alert])

    # Wait for second workflow execution
    second_workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID,
        second_provisioned[0].id,
        exclude_ids=[first_execution_id],
    )

    # Verify second execution was also successful
    assert len(workflow_manager.scheduler.workflows_to_run) == 0
    assert second_workflow_execution is not None
    assert second_workflow_execution.status == "success"
    assert second_workflow_execution.id != first_execution_id  # Different execution ID
    assert (
        second_workflow_execution.workflow_id == second_provisioned[0].id
    )  # Same workflow ID
