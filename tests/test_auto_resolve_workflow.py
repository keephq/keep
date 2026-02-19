from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from keep.api.bl.incidents_bl import IncidentBl
from keep.api.models.alert import AlertStatus, AlertSeverity
from keep.api.models.db.alert import Alert
from keep.api.models.db.incident import Incident, IncidentStatus, IncidentSeverity
from keep.api.models.db.rule import ResolveOn
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.core.db import add_alerts_to_incident

def test_auto_resolve_sends_workflow_event(db_session, create_alert):
    # 1. Create an incident that resolves on ALL resolved
    incident_id = uuid4()
    incident = Incident(
        id=incident_id,
        tenant_id=SINGLE_TENANT_UUID,
        status=IncidentStatus.FIRING.value,
        severity=IncidentSeverity.CRITICAL.value,
        message="Test Incident",
        description="Test Description",
        created_at=datetime.now(timezone.utc),
        resolve_on=ResolveOn.ALL.value,
        user_generated_name="Test Incident",
    )
    db_session.add(incident)
    db_session.flush()

    # 2. Create a resolved alert linked to it
    # Note: create_alert(fingerprint, status, timestamp, extras)
    create_alert(
        "test-alert-1",
        AlertStatus.RESOLVED,
        datetime.now(timezone.utc),
        {"severity": AlertSeverity.CRITICAL.value}
    )
    alert = db_session.query(Alert).filter(Alert.fingerprint == "test-alert-1").first()

    
    # Link alert to incident
    add_alerts_to_incident(SINGLE_TENANT_UUID, incident, [alert.fingerprint], session=db_session)
    
    # Verify incident is currently firing (setup check)
    assert incident.status == IncidentStatus.FIRING.value

    # 3. Instantiate IncidentBl
    incident_bl = IncidentBl(SINGLE_TENANT_UUID, db_session)

    # 4. Mock WorkflowManager
    with patch("keep.workflowmanager.workflowmanager.WorkflowManager.get_instance") as mock_get_instance:
        mock_wm = MagicMock()
        mock_get_instance.return_value = mock_wm
        
        # 5. Call resolve_incident_if_require
        # This function updates the incident in DB if rule is met
        updated_incident = incident_bl.resolve_incident_if_require(incident)
        
        # 6. Verify status changed to RESOLVED
        assert updated_incident.status == IncidentStatus.RESOLVED.value
        
        # 7. Verify insert_incident was called with "updated"
        # This is expected to FAIL without the fix
        mock_wm.insert_incident.assert_called_once()
        args, kwargs = mock_wm.insert_incident.call_args
        assert args[0] == SINGLE_TENANT_UUID
        # args[1] is the incident dto
        assert args[2] == "updated" # action

def test_auto_resolve_workflow_suppression(db_session, create_alert):
    # 1. Create incident
    incident_id = uuid4()
    incident = Incident(
        id=incident_id,
        tenant_id=SINGLE_TENANT_UUID,
        status=IncidentStatus.FIRING.value,
        severity=IncidentSeverity.CRITICAL.value,
        message="Test Incident",
        description="Test Description",
        created_at=datetime.now(timezone.utc),
        resolve_on=ResolveOn.ALL.value,
        user_generated_name="Test Incident",
    )
    db_session.add(incident)
    db_session.flush()

    # 2. Add resolved alert
    create_alert(
        "test-alert-2",
        AlertStatus.RESOLVED,
        datetime.now(timezone.utc),
        {"severity": AlertSeverity.CRITICAL.value}
    )
    alert = db_session.query(Alert).filter(Alert.fingerprint == "test-alert-2").first()
    add_alerts_to_incident(SINGLE_TENANT_UUID, incident, [alert.fingerprint], session=db_session)
    
    incident_bl = IncidentBl(SINGLE_TENANT_UUID, db_session)

    # 3. Test handle_workflow_event=False
    with patch("keep.workflowmanager.workflowmanager.WorkflowManager.get_instance") as mock_get_instance:
        mock_wm = MagicMock()
        mock_get_instance.return_value = mock_wm
        
        # Call with flag=False
        updated_incident = incident_bl.resolve_incident_if_require(
            incident, 
            handle_workflow_event=False
        )
        
        assert updated_incident.status == IncidentStatus.RESOLVED.value
        
        # Verify NO workflow triggered
        mock_wm.insert_incident.assert_not_called()
