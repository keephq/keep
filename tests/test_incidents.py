from datetime import datetime
from itertools import cycle

import pytest
from sqlalchemy import func
from sqlalchemy.orm.exc import DetachedInstanceError

from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_alerts_data_for_incident,
    get_incident_by_id,
    remove_alerts_to_incident_by_incident_id,
    get_last_incidents, IncidentSorting, get_last_alerts,
)
from keep.api.core.db_utils import get_json_extract_field
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import IncidentSeverity, AlertSeverity, AlertStatus, IncidentStatus
from keep.api.models.db.alert import Alert
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from tests.fixtures.client import client, test_app

def test_get_alerts_data_for_incident(db_session, setup_stress_alerts_no_elastic):
    alerts = setup_stress_alerts_no_elastic(100)
    assert 100 == db_session.query(func.count(Alert.id)).scalar()

    data = get_alerts_data_for_incident([a.id for a in alerts])
    assert data["sources"] == set(["source_{}".format(i) for i in range(10)])
    assert data["services"] == set(["service_{}".format(i) for i in range(10)])
    assert data["count"] == 100


def test_add_remove_alert_to_incidents(db_session, setup_stress_alerts_no_elastic):
    alerts = setup_stress_alerts_no_elastic(100)
    incident = create_incident_from_dict(SINGLE_TENANT_UUID, {"user_generated_name": "test", "user_summary": "test"})

    assert len(incident.alerts) == 0

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [a.id for a in alerts]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(10)])
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(10)])

    service_field = get_json_extract_field(db_session, Alert.event, 'service')

    service_0 = (
        db_session.query(Alert.id)
        .filter(
            service_field == "service_0"
        )
        .all()
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [service_0[0].id, ]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 99
    assert "service_0" in incident.affected_services
    assert len(incident.affected_services) == 10
    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(10)])

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [a.id for a in service_0]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 90
    assert "service_0" not in incident.affected_services
    assert len(incident.affected_services) == 9
    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(1, 10)])

    source_1 = (
        db_session.query(Alert.id)
        .filter(
            Alert.provider_type == "source_1"
        )
        .all()
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [source_1[0].id, ]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 89
    assert "source_1" in incident.sources
    # source_0 was removed together with service_0
    assert len(incident.sources) == 9
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(1, 10)])

    remove_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [a.id for a in source_1]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.sources) == 8
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(2, 10)])


def test_get_last_incidents(db_session, create_alert):

    severity_cycle = cycle([IncidentSeverity.from_number(s).order for s in range(1, 6)])

    for i in range(50):
        severity = next(severity_cycle)
        incident = create_incident_from_dict(SINGLE_TENANT_UUID, {
            "user_generated_name": f"test-{i}",
            "user_summary": f"test-{i}",
            "is_confirmed": True,
            "severity": severity
        })
        create_alert(f"alert-test-{i}", AlertStatus.FIRING, datetime.utcnow(), {"severity": AlertSeverity.from_number(severity)})
        alert = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

        add_alerts_to_incident_by_incident_id(
           SINGLE_TENANT_UUID,
           incident.id,
           [alert.id]
        )

    incidents_default, incidents_default_count = get_last_incidents(SINGLE_TENANT_UUID)
    assert len(incidents_default) == 0
    assert incidents_default_count == 0

    incidents_confirmed, incidents_confirmed_count = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True)
    assert len(incidents_confirmed) == 25
    assert incidents_confirmed_count == 50
    for i in range(25):
        assert incidents_confirmed[i].user_generated_name == f"test-{i}"

    incidents_limit_5, incidents_count_limit_5 = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, limit=5)
    assert len(incidents_limit_5) == 5
    assert incidents_count_limit_5 == 50
    for i in range(5):
        assert incidents_limit_5[i].user_generated_name == f"test-{i}"

    incidents_limit_5_page_2, incidents_count_limit_5_page_2 = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, limit=5, offset=5)

    assert len(incidents_limit_5_page_2) == 5
    assert incidents_count_limit_5_page_2 == 50
    for i, j in enumerate(range(5, 10)):
        assert incidents_limit_5_page_2[i].user_generated_name == f"test-{j}"

    # If alerts not preloaded, we will have detached session issue during attempt to get them
    # Background on this error at: https://sqlalche.me/e/14/bhk3
    with pytest.raises(DetachedInstanceError):
        alerts = incidents_confirmed[0].alerts

    incidents_with_alerts, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, with_alerts=True)
    for i in range(25):
        assert len(incidents_with_alerts[i].alerts) == 1

    # Test sorting

    incidents_sorted_by_severity, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, sorting=IncidentSorting.severity, limit=5)
    assert all([i.severity == IncidentSeverity.LOW.order for i in incidents_sorted_by_severity])

    incidents_sorted_by_severity_desc, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, sorting=IncidentSorting.severity_desc, limit=5)
    assert all([i.severity == IncidentSeverity.CRITICAL.order for i in incidents_sorted_by_severity_desc])

@pytest.mark.parametrize(
    "test_app", ["NO_AUTH"], indirect=True
)
def test_incident_status_change(db_session, client, test_app, setup_stress_alerts_no_elastic):

    alerts = setup_stress_alerts_no_elastic(100)
    incident = create_incident_from_dict("keep", {"name": "test", "description": "test"})

    add_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [a.id for a in alerts]
    )

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert len([alert for alert in alerts_dtos if alert.status == AlertStatus.RESOLVED.value]) == 0

    response_ack = client.post(
        "/incidents/{}/status".format(incident.id),
        headers={"x-api-key": "some-key"},
        json={
            "status": IncidentStatus.ACKNOWLEDGED.value,
        }
    )

    assert response_ack.status_code == 200
    data = response_ack.json()
    assert data["id"] == str(incident.id)
    assert data["status"] == IncidentStatus.ACKNOWLEDGED.value

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    assert incident.status == IncidentStatus.ACKNOWLEDGED.value
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert len([alert for alert in alerts_dtos if alert.status == AlertStatus.RESOLVED.value]) == 0

    response_resolved = client.post(
        "/incidents/{}/status".format(incident.id),
        headers={"x-api-key": "some-key"},
        json={
            "status": IncidentStatus.RESOLVED.value,
        }
    )

    assert response_resolved.status_code == 200
    data = response_resolved.json()
    assert data["id"] == str(incident.id)
    assert data["status"] == IncidentStatus.RESOLVED.value

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    assert incident.status == IncidentStatus.RESOLVED.value
    # All alerts are resolved as well
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert len([alert for alert in alerts_dtos if alert.status == AlertStatus.RESOLVED.value]) == 100
