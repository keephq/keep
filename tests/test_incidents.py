from datetime import datetime
from itertools import cycle

import pytest
from sqlalchemy import func, distinct
from sqlalchemy.orm.exc import DetachedInstanceError

from keep.api.core.db import (
    IncidentSorting,
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_alerts_data_for_incident,
    get_incident_by_id,
    get_last_incidents,
    remove_alerts_to_incident_by_incident_id,
    get_incident_alerts_by_incident_id
)
from keep.api.core.db_utils import get_json_extract_field
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import (
    AlertSeverity,
    AlertStatus,
    IncidentSeverity,
    IncidentStatus,
)
from keep.api.models.db.alert import Alert, AlertToIncident
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from tests.fixtures.client import client, test_app  # noqa


def test_get_alerts_data_for_incident(db_session, create_alert):
    for i in range(100):
        create_alert(
            f"alert-test-{i % 10}",
            AlertStatus.FIRING,
            datetime.utcnow(),
            {
                "source": [f"source_{i % 10}"],
                "service": f"service_{i % 10}",
            }
        )

    alerts = db_session.query(Alert).all()

    unique_fingerprints = db_session.query(func.count(distinct(Alert.fingerprint))).scalar()

    assert 100 == db_session.query(func.count(Alert.id)).scalar()
    assert 10 == unique_fingerprints

    data = get_alerts_data_for_incident([a.id for a in alerts])
    assert data["sources"] == set([f"source_{i}" for i in range(10)])
    assert data["services"] == set([f"service_{i}" for i in range(10)])
    assert data["count"] == unique_fingerprints


def test_add_remove_alert_to_incidents(db_session, setup_stress_alerts_no_elastic):
    alerts = setup_stress_alerts_no_elastic(100)
    # Adding 10 non-unique fingerprints
    alerts.extend(setup_stress_alerts_no_elastic(10))
    incident = create_incident_from_dict(
        SINGLE_TENANT_UUID, {"user_generated_name": "test", "user_summary": "test"}
    )

    assert len(incident.alerts) == 0

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [a.id for a in alerts]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    # 110 alerts
    assert len(incident.alerts) == 110
    # But 100 unique fingerprints
    assert incident.alerts_count == 100

    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(10)]
    )
    assert sorted(incident.sources) == sorted(
        ["source_{}".format(i) for i in range(10)]
    )

    service_field = get_json_extract_field(db_session, Alert.event, "service")

    service_0 = db_session.query(Alert.id).filter(service_field == "service_0").all()

    # Testing unique fingerprints
    more_alerts_with_same_fingerprints = setup_stress_alerts_no_elastic(10)

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [a.id for a in more_alerts_with_same_fingerprints]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert incident.alerts_count == 100
    assert db_session.query(func.count(AlertToIncident.alert_id)).scalar() == 120

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [
            service_0[0].id,
        ],
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    # 117 because we removed multiple alerts with service_0
    assert len(incident.alerts) == 117
    assert "service_0" in incident.affected_services
    assert len(incident.affected_services) == 10
    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(10)]
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [a.id for a in service_0]
    )

    # Removing shouldn't impact links between alert and incident if include_unlinked=True
    assert len(get_incident_alerts_by_incident_id(
        incident_id=incident.id,
        tenant_id=incident.tenant_id,
        include_unlinked=True
    )[0]) == 120

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    # 108 because we removed multiple alert with same fingerprints
    assert len(incident.alerts) == 108
    assert "service_0" not in incident.affected_services
    assert len(incident.affected_services) == 9
    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(1, 10)]
    )

    source_1 = (
        db_session.query(Alert.id).filter(Alert.provider_type == "source_1").all()
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [
            source_1[0].id,
        ],
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 105
    assert "source_1" in incident.sources
    # source_0 was removed together with service_0
    assert len(incident.sources) == 9
    assert sorted(incident.sources) == sorted(
        ["source_{}".format(i) for i in range(1, 10)]
    )

    remove_alerts_to_incident_by_incident_id(
        "keep", incident.id, [a.id for a in source_1]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.sources) == 8
    assert sorted(incident.sources) == sorted(
        ["source_{}".format(i) for i in range(2, 10)]
    )




def test_get_last_incidents(db_session, create_alert):

    severity_cycle = cycle([s.order for s in IncidentSeverity])
    status_cycle = cycle([s.value for s in IncidentStatus])
    services_cycle = cycle(["keep", None])

    for i in range(50):
        severity = next(severity_cycle)
        status = next(status_cycle)
        incident = create_incident_from_dict(SINGLE_TENANT_UUID, {
            "user_generated_name": f"test-{i}",
            "user_summary": f"test-{i}",
            "is_confirmed": True,
            "severity": severity,
            "status": status,
        })
        create_alert(
            f"alert-test-{i}",
            AlertStatus(status),
            datetime.utcnow(),
            {
                "severity": AlertSeverity.from_number(severity),
                "service": next(services_cycle),
            }
        )
        alert = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

        add_alerts_to_incident_by_incident_id(
            SINGLE_TENANT_UUID, incident.id, [alert.id]
        )

    incidents_default, incidents_default_count = get_last_incidents(SINGLE_TENANT_UUID)
    assert len(incidents_default) == 0
    assert incidents_default_count == 0

    incidents_confirmed, incidents_confirmed_count = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True
    )
    assert len(incidents_confirmed) == 25
    assert incidents_confirmed_count == 50
    for i in range(25):
        assert incidents_confirmed[i].user_generated_name == f"test-{i}"

    incidents_limit_5, incidents_count_limit_5 = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, limit=5
    )
    assert len(incidents_limit_5) == 5
    assert incidents_count_limit_5 == 50
    for i in range(5):
        assert incidents_limit_5[i].user_generated_name == f"test-{i}"

    incidents_limit_5_page_2, incidents_count_limit_5_page_2 = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, limit=5, offset=5
    )

    assert len(incidents_limit_5_page_2) == 5
    assert incidents_count_limit_5_page_2 == 50
    for i, j in enumerate(range(5, 10)):
        assert incidents_limit_5_page_2[i].user_generated_name == f"test-{j}"

    # If alerts not preloaded, we will have detached session issue during attempt to get them
    # Background on this error at: https://sqlalche.me/e/14/bhk3
    with pytest.raises(DetachedInstanceError):
        alerts = incidents_confirmed[0].alerts  # noqa

    incidents_with_alerts, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, with_alerts=True
    )
    for i in range(25):
        assert len(incidents_with_alerts[i].alerts) == 1

    # Test sorting

    incidents_sorted_by_severity, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, sorting=IncidentSorting.severity, limit=5
    )
    assert all(
        [i.severity == IncidentSeverity.LOW.order for i in incidents_sorted_by_severity]
    )

    # Test filters

    filters_1 = {"severity": [1]}
    incidents_with_filters_1, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_1, limit=100)
    assert len(incidents_with_filters_1) == 10
    assert all([i.severity == 1 for i in incidents_with_filters_1])

    filters_2 = {"status": ["firing", "acknowledged"]}
    incidents_with_filters_2, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_2, limit=100)
    assert len(incidents_with_filters_2) == 17 + 16
    assert all([i.status in ["firing", "acknowledged"] for i in incidents_with_filters_2])

    filters_3 = {"sources": ["keep"]}
    incidents_with_filters_3, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_3, limit=100)
    assert len(incidents_with_filters_3) == 50
    assert all(["keep" in i.sources for i in incidents_with_filters_3])

    filters_4 = {"sources": ["grafana"]}
    incidents_with_filters_4, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_4, limit=100)
    assert len(incidents_with_filters_4) == 0
    filters_5 = {"affected_services": "keep"}
    incidents_with_filters_5, _ = get_last_incidents(SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_5, limit=100)
    assert len(incidents_with_filters_5) == 25
    assert all(["keep" in i.affected_services for i in incidents_with_filters_5])



@pytest.mark.parametrize(
    "test_app", ["NO_AUTH"], indirect=True
)
def test_incident_status_change(db_session, client, test_app, setup_stress_alerts_no_elastic):

    alerts = setup_stress_alerts_no_elastic(100)
    incident = create_incident_from_dict(
        "keep", {"name": "test", "description": "test"}
    )

    add_alerts_to_incident_by_incident_id("keep", incident.id, [a.id for a in alerts])

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert (
        len(
            [
                alert
                for alert in alerts_dtos
                if alert.status == AlertStatus.RESOLVED.value
            ]
        )
        == 0
    )

    response_ack = client.post(
        "/incidents/{}/status".format(incident.id),
        headers={"x-api-key": "some-key"},
        json={
            "status": IncidentStatus.ACKNOWLEDGED.value,
        },
    )

    assert response_ack.status_code == 200
    data = response_ack.json()
    assert data["id"] == str(incident.id)
    assert data["status"] == IncidentStatus.ACKNOWLEDGED.value

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    assert incident.status == IncidentStatus.ACKNOWLEDGED.value
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert (
        len(
            [
                alert
                for alert in alerts_dtos
                if alert.status == AlertStatus.RESOLVED.value
            ]
        )
        == 0
    )

    response_resolved = client.post(
        "/incidents/{}/status".format(incident.id),
        headers={"x-api-key": "some-key"},
        json={
            "status": IncidentStatus.RESOLVED.value,
        },
    )

    assert response_resolved.status_code == 200
    data = response_resolved.json()
    assert data["id"] == str(incident.id)
    assert data["status"] == IncidentStatus.RESOLVED.value

    incident = get_incident_by_id("keep", incident.id, with_alerts=True)

    assert incident.status == IncidentStatus.RESOLVED.value
    # All alerts are resolved as well
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident.alerts)
    assert (
        len(
            [
                alert
                for alert in alerts_dtos
                if alert.status == AlertStatus.RESOLVED.value
            ]
        )
        == 100
    )


@pytest.mark.parametrize(
    "test_app", ["NO_AUTH"], indirect=True
)
def test_incident_metadata(db_session, client, test_app, setup_stress_alerts_no_elastic):
    severity_cycle = cycle([s.order for s in IncidentSeverity])
    status_cycle = cycle([s.value for s in IncidentStatus])
    sources_cycle = cycle(["keep", "keep-test", "keep-test-2"])
    services_cycle = cycle(["keep", "keep-test", "keep-test-2"])

    for i in range(50):
        severity = next(severity_cycle)
        status = next(status_cycle)
        service = next(services_cycle)
        source = next(sources_cycle)
        create_incident_from_dict(SINGLE_TENANT_UUID, {
            "user_generated_name": f"test-{i}",
            "user_summary": f"test-{i}",
            "is_confirmed": True,
            "assignee": f"assignee-{i % 5}",
            "severity": severity,
            "status": status,
            "sources": [source],
            "affected_services": [service],
        })

    response = client.get(
        "/incidents/meta/",
        headers={"x-api-key": "some-key"},
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 5
    assert "statuses" in data
    assert data["statuses"] == [s.value for s in IncidentStatus]
    assert "severities" in data
    assert data["severities"] == [s.value for s in IncidentSeverity]
    assert "assignees" in data
    assert data["assignees"] == [f"assignee-{i}" for i in range(5)]
    assert "services" in data
    assert data["services"] == ["keep", "keep-test", "keep-test-2"]
    assert "sources" in data
    assert data["sources"] == ["keep", "keep-test", "keep-test-2"]


def test_add_alerts_with_same_fingerprint_to_incident(db_session, create_alert):
    create_alert(
        "fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        f"fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        f"fp2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    db_alerts = db_session.query(Alert).all()

    fp1_alerts = [alert for alert in db_alerts if alert.fingerprint == "fp1"]
    fp2_alerts = [alert for alert in db_alerts if alert.fingerprint == "fp2"]

    assert len(db_alerts) == 3
    assert len(fp1_alerts) == 2
    assert len(fp2_alerts) == 1

    incident = create_incident_from_dict(
        SINGLE_TENANT_UUID, {"user_generated_name": "test", "user_summary": "test"}
    )

    assert len(incident.alerts) == 0

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [fp1_alerts[0].id]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 2

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [fp1_alerts[0].id]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert len(incident.alerts) == 0

