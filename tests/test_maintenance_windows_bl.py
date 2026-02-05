from datetime import datetime, timedelta
import importlib
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import keep.api.consts
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.core.db import get_alerts_by_status, get_workflow_executions, get_workflow_executions_count
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert
from keep.api.models.db.maintenance_window import MaintenanceRuleCreate, MaintenanceWindowRule
from keep.api.models.db.workflow import Workflow
from keep.api.routes.maintenance import update_maintenance_rule
from keep.functions import cyaml
from keep.workflowmanager.workflowstore import WorkflowStore
from tests.fixtures.workflow_manager import (
    workflow_manager,
    wait_for_workflow_execution,
)


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def active_maintenance_window_rule_custom_ignore():
    return MaintenanceWindowRule(
        id=1,
        name="Active maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        enabled=True,
        ignore_statuses=[AlertStatus.FIRING.value,],
    )


@pytest.fixture
def active_maintenance_window_rule():
    return MaintenanceWindowRule(
        id=1,
        name="Active maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        enabled=True,
        ignore_statuses=[AlertStatus.RESOLVED.value, AlertStatus.ACKNOWLEDGED.value],
    )


@pytest.fixture
def active_maintenance_window_rule_with_suppression_on():
    return MaintenanceWindowRule(
        id=1,
        name="Active maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=1),
        enabled=True,
        suppress=True,
    )


@pytest.fixture
def expired_maintenance_window_rule_with_suppression_on():
    return MaintenanceWindowRule(
        id=1,
        name="Expired maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(hours=5),
        end_time=datetime.utcnow() - timedelta(hours=1),
        enabled=False,
        suppress=True,
    )


@pytest.fixture
def expired_maintenance_window_rule():
    return MaintenanceWindowRule(
        id=2,
        name="Expired maintenance_window",
        tenant_id="test-tenant",
        cel_query='source == "test-source"',
        start_time=datetime.utcnow() - timedelta(days=2),
        end_time=datetime.utcnow() - timedelta(days=1),
        enabled=True,
    )


@pytest.fixture
def alert_dto():
    return AlertDto(
        id="test-alert",
        source=["test-source"],
        name="Test Alert",
        status="firing",
        severity="critical",
        lastReceived="2021-08-01T00:00:00Z",
    )

@pytest.fixture
def alert_maint():
    return Alert(
        id=uuid4(),
        tenant_id="test-tenant",
        fingerprint="test-fingerprint",
        provider_id="test-provider",
        provider_type="test-provider-type",
        event={
            "name": "Test Alert",
            "status": AlertStatus.MAINTENANCE.value,
            "previous_status": AlertStatus.FIRING.value,
            "source": ["test-source"],
        },
        alert_hash="test-alert-hash",
    )


def test_alert_in_active_maintenance_window(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Simulate the query to return the active maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is True


def test_alert_in_active_maintenance_window_with_suppress(
    mock_session, active_maintenance_window_rule_with_suppression_on, alert_dto, monkeypatch
):
    # Ensure we use the default strategy (not recover_previous_status from other tests)
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "default")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    
    # Simulate the query to return the active maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule_with_suppression_on
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False
    assert alert_dto.status == AlertStatus.SUPPRESSED.value


def test_alert_not_in_expired_maintenance_window(
    mock_session, expired_maintenance_window_rule, alert_dto
):
    # Simulate the query to return the expired maintenance_window
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        expired_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Even though the query returned a maintenance_window, it should not match because it's expired
    assert result is False


def test_alert_in_no_maintenance_window(mock_session, alert_dto):
    # Simulate the query to return no maintenance_windows
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = (
        []
    )

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False


def test_alert_in_maintenance_window_with_non_matching_cel(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Modify the cel_query so that the alert won't match
    active_maintenance_window_rule.cel_query = 'source == "other-source"'
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    assert result is False


def test_alert_ignored_due_to_resolved_status(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Set the alert status to RESOLVED
    alert_dto.status = "resolved"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the alert status is RESOLVED
    assert result is False


def test_alert_ignored_due_to_acknowledged_status(
    mock_session, active_maintenance_window_rule, alert_dto
):
    # Set the alert status to ACKNOWLEDGED
    alert_dto.status = "acknowledged"

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the alert status is ACKNOWLEDGED
    assert result is False


def test_alert_with_missing_cel_field(mock_session, active_maintenance_window_rule, alert_dto):
    # Modify the cel_query to reference a non-existent field
    active_maintenance_window_rule.cel_query = 'alertname == "test-alert"'
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # Should return False because the field doesn't exist
    assert result is False


def test_alert_not_ignored_due_to_custom_status(
    mock_session, active_maintenance_window_rule_custom_ignore, alert_dto
):
    # Set the alert status to RESOLVED

    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule_custom_ignore
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )

    # Should return False because the alert status is FIRING
    alert_dto.status = AlertStatus.FIRING.value
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)
    assert result is False

    alert_dto.status = AlertStatus.RESOLVED.value
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)
    assert result is True


def test_strategy_restore_update_status(
    mock_session, active_maintenance_window_rule_with_suppression_on, alert_dto, monkeypatch
):
    """
    Feature: Strategy - recover previous status
    Scenario: Alert enters in maintenance window with suppression
    """
    # GIVEN The strategy is recover_previous_status
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    # AND there is a maintenance window rule with suppression on active
    mock_session.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
        active_maintenance_window_rule_with_suppression_on
    ]

    maintenance_window_bl = MaintenanceWindowsBl(
        tenant_id="test-tenant", session=mock_session
    )

    # WHEN it checks if the alert is in maintenance windows
    result = maintenance_window_bl.check_if_alert_in_maintenance_windows(alert_dto)

    # THEN the result should be False
    assert result is False
    # AND the previous status should be set old alert status
    assert alert_dto.previous_status == AlertStatus.FIRING.value
    # AND the current status should be set to MAINTENANCE
    assert alert_dto.status == AlertStatus.MAINTENANCE.value

def test_strategy_clean_status(
    mock_session, alert_maint, monkeypatch, expired_maintenance_window_rule_with_suppression_on
):
    """
    Feature: Strategy - recover previous status
    Scenario: Alert recovers previous status after maintenance window ends. Whitout any window active.
    """
    # GIVEN The strategy is recover_previous_status
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    # AND there is a maintenance window expired.
    retrieve_windows_session = MagicMock()
    retrieve_windows_session.exec.return_value.all.return_value = [
        expired_maintenance_window_rule_with_suppression_on
    ]
    # AND there is an alert which was received inside a maintenance window
    retrieve_alerts_session = MagicMock()
    retrieve_alerts_session.exec.return_value.all.return_value = [alert_maint]

    recover_status_session = MagicMock()
    recover_status_session.exec = MagicMock()
    recover_status_session.commit = MagicMock()

    # AND there is a last alert with the same FP
    mock_last_alert = MagicMock()
    mock_last_alert.alert_id = alert_maint.id
    mock_last_alert.event = {"alert_id": alert_maint.id}

    # WHEN recover its previous status
    mock_session.__enter__.side_effect = [retrieve_windows_session, retrieve_alerts_session, recover_status_session, MagicMock(),  MagicMock()]
    with patch("keep.api.core.db.existed_or_new_session", return_value=mock_session), \
            patch("keep.api.bl.maintenance_windows_bl.get_last_alert_by_fingerprint", return_value=mock_last_alert), \
                patch("keep.api.core.db.get_alert_by_event_id", return_value=alert_maint):
        
        MaintenanceWindowsBl.recover_strategy(logger=MagicMock(), session=mock_session)

    # THEN the new status will be the previous status, and the previous status will be the old status
    _, new_status, new_previous_status, _ = list(recover_status_session.exec.call_args[0][0]._values.values())[0].value.values()
    assert new_status == AlertStatus.FIRING.value
    assert new_previous_status == AlertStatus.MAINTENANCE.value


def test_strategy_alert_block_by_window(
    mock_session, active_maintenance_window_rule_with_suppression_on, alert_maint, monkeypatch
):
    """
    Feature: Strategy - recover previous status
    Scenario: Alert is blocked (continue with the same status) by maintenance window
    """
    # GIVEN The strategy is recover_previous_status
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    # AND there is a maintenance window active
    retrieve_windows_session = MagicMock()
    retrieve_windows_session.exec.return_value.all.return_value = [active_maintenance_window_rule_with_suppression_on]
    # AND there is an alert which was received inside a maintenance window
    retrieve_alerts_session = MagicMock()
    retrieve_alerts_session.exec.return_value.all.return_value = [alert_maint]

    recover_status_session = MagicMock()
    recover_status_session.exec = MagicMock()
    recover_status_session.commit = MagicMock()

    loggerMag = MagicMock()
    # WHEN the conditions match to recover the initial alert status
    mock_session.__enter__.side_effect = [retrieve_windows_session, retrieve_alerts_session, recover_status_session, MagicMock()]
    with patch("keep.api.core.db.existed_or_new_session", return_value=mock_session):
        MaintenanceWindowsBl.recover_strategy(logger=loggerMag, session=mock_session)

    # THEN the update status method will not be called
    assert not recover_status_session.exec.called
    # AND logger alert will rise an info about the alert blocked by maintenance window
    loggerMag.info.assert_any_call(
            "Alert %s is blocked due to the maintenance window: %s.", alert_maint.id,
            active_maintenance_window_rule_with_suppression_on.id
        )

def test_strategy_alert_expired_by_current_time(
    create_alert, db_session, monkeypatch, create_window_maintenance_active
):
    """
    Feature: Strategy - recover previous status
    Scenario: Having a Maintenance window active, receiving new alerts in that window,
             when the window expires by current time, the alerts should recover its previous status.
    """
    # GIVEN The strategy is recover_previous_status
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    # AND there is a maintenance window active.
    mw = create_window_maintenance_active(
        cel='fingerprint == "alert-test-1" || fingerprint == "alert-test-2"',
        start=datetime.utcnow() - timedelta(hours=10),
        end=datetime.utcnow() + timedelta(days=1),
    )

    #AND there are new alerts
    create_alert(
        "alert-test-1",
        AlertStatus("firing"),
        datetime.utcnow(),
        {},
    )
    create_alert(
        "alert-test-2",
        AlertStatus("firing"),
        datetime.utcnow(),
        {},
    )
    MaintenanceWindowsBl.recover_strategy(logger=MagicMock(), session=db_session)
    maintenance_status_prev = get_alerts_by_status(AlertStatus.MAINTENANCE, db_session)
    #WHEN The Maintenance Window is closed, because the end time is < current time
    update_maintenance_rule(
        rule_id=mw.id,
        rule_dto=MaintenanceRuleCreate(
            name=mw.name,
            cel_query=mw.cel_query,
            start_time=mw.start_time,
            duration_seconds=36000-5,  # 10h - 5 seconds duration, so the end is just before current time
        ),
        authenticated_entity=MagicMock(tenant_id=SINGLE_TENANT_UUID, email="test@keephq.dev"),
        session=db_session
    )
    time.sleep(3)
    MaintenanceWindowsBl.recover_strategy(logger=MagicMock(), session=db_session)

    #THEN There are 2 alert prev to the current hour and 0 after the maintenance window is expired
    maintenance_status_post = get_alerts_by_status(AlertStatus.MAINTENANCE, db_session)
    assert len(maintenance_status_prev) == 2
    assert len(maintenance_status_post) == 0

@pytest.mark.parametrize(
    ["solved_alert", "executions"],
    [
        (True, 0),
        (False, 1),
    ],
)
def test_strategy_alert_execution_wf(
    create_alert, db_session, monkeypatch, create_window_maintenance_active, workflow_manager,
    solved_alert, executions
):
    """
    Feature: Strategy - recover previous status with Workflow execution
    Scenario: Having a WF created and a Maintenance window active, 
             receiving in that window 3 alerts (same FP), 2 FIRING and the other 
             one in RESOLVED status, the WF is not executed at the end of the
             maintenance window.

             On the other hand, receiving 2 alerts(same FP) inside the maintenance window,
             once it's expired, the WF is executed 1 time.
    """
    # GIVEN The strategy is recover_previous_status
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    #AND A Workflow ready to be executed
    workflow_definition = """
        workflow:
            id: 123-333-22-11-22
            name: WF_alert-test-1
            description: Description
            disabled: false
            triggers:
            - type: alert
              cel: fingerprint == "alert-test-1" && status == "firing"
            inputs: []
            consts: {}
            owners: []
            services: []
            steps: []
            actions:
            - name: action-mock
              provider:
                type: mock
                config: "{{ providers.default-mock }}"
                with:
                    enrich_alert:
                        - key: extra_field
                          value: workflow_executed
        """
    workflow_data = cyaml.safe_load(workflow_definition)
    workflow = WorkflowStore().create_workflow(
            tenant_id=SINGLE_TENANT_UUID,
            created_by="keep",
            workflow=workflow_data.pop("workflow"),
        )
    #AND A Maintenance window active
    mw = create_window_maintenance_active(
        cel='fingerprint == "alert-test-1"',
        start=datetime.utcnow() - timedelta(hours=10),
        end=datetime.utcnow() + timedelta(days=1),
    )

    # AND 2 Firing alerts with the same Fingerprint
    create_alert(
        "alert-test-1",
        AlertStatus("firing"),
        datetime.utcnow(),
        {},
    )
    create_alert(
        "alert-test-1",
        AlertStatus("firing"),
        datetime.utcnow(),
        {},
    )
    if solved_alert:
        #AND 1 Resolved alert with the same Fingerprint
        create_alert(
            "alert-test-1",
            AlertStatus("resolved"),
            datetime.utcnow(),
            {},
        )
    time.sleep(1)
    MaintenanceWindowsBl.recover_strategy(logger=MagicMock(), session=db_session)
    #WHEN The Maintenance Window is closed, because the end time is < current time
    update_maintenance_rule(
        rule_id=mw.id,
        rule_dto=MaintenanceRuleCreate(
            name=mw.name,
            cel_query=mw.cel_query,
            start_time=mw.start_time,
            duration_seconds=36000-5,  # 10h - 5 seconds duration, so the end is just before current time
        ),
        authenticated_entity=MagicMock(tenant_id=SINGLE_TENANT_UUID, email="test@keephq.dev"),
        session=db_session
    )
    MaintenanceWindowsBl.recover_strategy(logger=MagicMock(), session=db_session)
    time.sleep(5)
    #THEN The WF is not executed if there is a resolved alert or executed 1 time if there are only firing alerts
    n_executions = get_workflow_executions(SINGLE_TENANT_UUID, workflow.id)[0]

    assert n_executions == executions