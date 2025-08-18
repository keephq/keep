from datetime import datetime, timedelta
import importlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import keep.api.consts
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.models.db.workflow import Workflow
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
    mock_session, active_maintenance_window_rule_with_suppression_on, alert_dto
):
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

    # WHEN recover its previous status
    mock_session.__enter__.side_effect = [retrieve_windows_session, retrieve_alerts_session, recover_status_session, MagicMock()]
    with patch("keep.api.core.db.existed_or_new_session", return_value=mock_session):
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
    # GIVEN The strategy is block_alert_by_maintenance_window
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

def test_strategy_alert_launch_workflow(
    mock_session, expired_maintenance_window_rule_with_suppression_on, alert_maint, monkeypatch, workflow_manager, db_session
):
    """
    Feature: Strategy - recover previous status
    Scenario: Having the Maintenance Window expired, the alert in its previous status, workflows should be launched.
    """
    # GIVEN The strategy is block_alert_by_maintenance_window
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "recover_previous_status")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)
    # AND a workflow matchs the alert attributes
    workflow_definition = """workflow:
                                id: 1
                                name: workflow_strategy_mw_test
                                description: "Description field"
                                disabled: false
                                triggers:
                                - type: alert
                                  cel: source == "test-source"
                                inputs: []
                                consts: {}
                                owners: []
                                services: []
                                actions:
                                - name: suppress_alerts
                                  provider:
                                    type: mock
                                    config: "{{ providers.default-mock }}"
                                    with:
                                        enrich_alert:
                                            - key: status
                                              value: acknowledged
                            """
    workflow = Workflow(
        id="workflow_strategy_mw",
        name="workflow_strategy_mw",
        tenant_id=alert_maint.tenant_id,
        description="Handle alerts based on startedAt timestamp",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_definition,
    )
    monkeypatch.setattr(
        "keep.workflowmanager.workflowstore.get_all_workflows",
        lambda tenant_id, exclude_disabled=False: [workflow]
    )
    monkeypatch.setattr(
        "keep.workflowmanager.workflowstore.get_workflow_by_id",
        lambda self, tenant_id, workflow_id="workflow_strategy_mw", exclude_disabled=False: workflow
    )
    # AND there is no maintenance window active
    retrieve_windows_session = MagicMock()
    retrieve_windows_session.exec.return_value.all.return_value = [expired_maintenance_window_rule_with_suppression_on]
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

    workflow_execution = wait_for_workflow_execution(
        alert_maint.tenant_id, "workflow_strategy_mw"
    )

    # THEN the workflow should be launched
    assert workflow_execution is not None
    assert workflow_execution.status == "success"