from datetime import datetime
from itertools import cycle

import pytest
from sqlalchemy import distinct, func, desc

from keep.api.bl.incidents_bl import IncidentBl
from keep.api.core.db import (
    IncidentSorting,
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_alerts_data_for_incident,
    get_incident_alerts_by_incident_id,
    get_incident_by_id,
    get_last_incidents,
    merge_incidents_to_id,
    remove_alerts_to_incident_by_incident_id,
)
from keep.api.core.db_utils import get_json_extract_field
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import (
    AlertSeverity,
    AlertStatus,
    IncidentSeverity,
    IncidentStatus,
)
from keep.api.models.db.alert import Alert, LastAlertToIncident
from keep.api.models.db.tenant import Tenant
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
            },
        )

    alerts = db_session.query(Alert).all()

    unique_fingerprints = db_session.query(
        func.count(distinct(Alert.fingerprint))
    ).scalar()

    assert 100 == db_session.query(func.count(Alert.id)).scalar()
    assert 10 == unique_fingerprints

    data = get_alerts_data_for_incident(
        SINGLE_TENANT_UUID, [a.fingerprint for a in alerts]
    )
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

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 0
    assert total_incident_alerts == 0

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [a.fingerprint for a in alerts]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 100
    assert total_incident_alerts == 100
    # But 100 unique fingerprints
    assert incident.alerts_count == 100

    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(10)]
    )
    assert sorted(incident.sources) == sorted(
        ["source_{}".format(i) for i in range(10)]
    )

    service_field = get_json_extract_field(db_session, Alert.event, "service")

    service_0 = (
        db_session.query(Alert.fingerprint).filter(service_field == "service_0").all()
    )

    # Testing unique fingerprints
    more_alerts_with_same_fingerprints = setup_stress_alerts_no_elastic(10)

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [a.fingerprint for a in more_alerts_with_same_fingerprints],
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    assert incident.alerts_count == 100
    assert db_session.query(func.count(LastAlertToIncident.fingerprint)).scalar() == 100

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [
            service_0[0].fingerprint,
        ],
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 99
    assert total_incident_alerts == 99

    assert "service_0" in incident.affected_services
    assert len(incident.affected_services) == 10
    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(10)]
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [a.fingerprint for a in service_0]
    )

    # Removing shouldn't impact links between alert and incident if include_unlinked=True
    assert (
        len(
            get_incident_alerts_by_incident_id(
                incident_id=incident.id,
                tenant_id=incident.tenant_id,
                include_unlinked=True,
            )[0]
        )
        == 100
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 90
    assert total_incident_alerts == 90

    assert "service_0" not in incident.affected_services
    assert len(incident.affected_services) == 9
    assert sorted(incident.affected_services) == sorted(
        ["service_{}".format(i) for i in range(1, 10)]
    )

    source_1 = (
        db_session.query(Alert.fingerprint)
        .filter(Alert.provider_type == "source_1")
        .all()
    )

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID,
        incident.id,
        [
            source_1[0].fingerprint,
        ],
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 89
    assert total_incident_alerts == 89

    assert "source_1" in incident.sources
    # source_0 was removed together with service_1
    assert len(incident.sources) == 9
    assert sorted(incident.sources) == sorted(
        ["source_{}".format(i) for i in range(1, 10)]
    )

    remove_alerts_to_incident_by_incident_id(
        "keep", incident.id, [a.fingerprint for a in source_1]
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

    for i in range(60):
        severity = next(severity_cycle)
        status = next(status_cycle)
        service = next(services_cycle)
        incident = create_incident_from_dict(
            SINGLE_TENANT_UUID,
            {
                "user_generated_name": f"test-{i}",
                "user_summary": f"test-{i}",
                "is_confirmed": True,
                "severity": severity,
                "status": status,
            },
        )
        # Merged incidents don't have alerts
        if status != IncidentStatus.MERGED.value:
            create_alert(
                f"alert-test-{i}",
                AlertStatus(status),
                datetime.utcnow(),
                {
                    "severity": AlertSeverity.from_number(severity),
                    "service": service,
                },
            )
            alert = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

            create_alert(
                f"alert-test-2-{i}",
                AlertStatus(status),
                datetime.utcnow(),
                {
                    "severity": AlertSeverity.from_number(severity),
                    "service": service,
                },
            )
            alert2 = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

            add_alerts_to_incident_by_incident_id(
                SINGLE_TENANT_UUID, incident.id, [alert.fingerprint, alert2.fingerprint]
            )

    incidents_default, incidents_default_count = get_last_incidents(SINGLE_TENANT_UUID)
    assert len(incidents_default) == 0
    assert incidents_default_count == 0

    incidents_confirmed, incidents_confirmed_count = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True
    )
    assert len(incidents_confirmed) == 25
    assert incidents_confirmed_count == 60
    for i in range(25):
        assert incidents_confirmed[i].user_generated_name == f"test-{i}"

    incidents_limit_5, incidents_count_limit_5 = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, limit=5
    )
    assert len(incidents_limit_5) == 5
    assert incidents_count_limit_5 == 60
    for i in range(5):
        assert incidents_limit_5[i].user_generated_name == f"test-{i}"

    incidents_limit_5_page_2, incidents_count_limit_5_page_2 = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, limit=5, offset=5
    )

    assert len(incidents_limit_5_page_2) == 5
    assert incidents_count_limit_5_page_2 == 60
    for i, j in enumerate(range(5, 10)):
        assert incidents_limit_5_page_2[i].user_generated_name == f"test-{j}"

    incidents_with_alerts, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, with_alerts=True
    )
    for i in range(25):
        if incidents_with_alerts[i].status == IncidentStatus.MERGED.value:
            assert len(incidents_with_alerts[i]._alerts) == 0
        else:
            assert len(incidents_with_alerts[i]._alerts) == 2

    # Test sorting

    incidents_sorted_by_severity, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, sorting=IncidentSorting.severity, limit=5
    )
    assert all(
        [i.severity == IncidentSeverity.LOW.order for i in incidents_sorted_by_severity]
    )

    # Test filters

    filters_1 = {"severity": [1]}
    incidents_with_filters_1, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_1, limit=100
    )
    assert len(incidents_with_filters_1) == 12
    assert all([i.severity == 1 for i in incidents_with_filters_1])

    filters_2 = {"status": ["firing", "acknowledged"]}
    incidents_with_filters_2, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_2, limit=100
    )
    assert (
        len(incidents_with_filters_2) == 15 + 15
    )  # 15 confirmed, 15 acknowledged because 60 incidents with cycled status
    assert all(
        [i.status in ["firing", "acknowledged"] for i in incidents_with_filters_2]
    )

    filters_3 = {"sources": ["keep"]}
    incidents_with_filters_3, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_3, limit=100
    )
    assert len(incidents_with_filters_3) == 45  # 60 minus 15 merged with no alerts
    assert all(["keep" in i.sources for i in incidents_with_filters_3])

    filters_4 = {"sources": ["grafana"]}
    incidents_with_filters_4, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_4, limit=100
    )
    assert len(incidents_with_filters_4) == 0
    filters_5 = {"affected_services": "keep"}
    incidents_with_filters_5, _ = get_last_incidents(
        SINGLE_TENANT_UUID, is_confirmed=True, filters=filters_5, limit=100
    )
    assert len(incidents_with_filters_5) == 30  # half of incidents
    assert all(["keep" in i.affected_services for i in incidents_with_filters_5])


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_incident_status_change(
    db_session, client, test_app, setup_stress_alerts_no_elastic
):

    alerts = setup_stress_alerts_no_elastic(100)
    incident = create_incident_from_dict(
        "keep", {"name": "test", "description": "test"}
    )

    add_alerts_to_incident_by_incident_id(
        "keep", incident.id, [a.fingerprint for a in alerts], session=db_session
    )

    incident = get_incident_by_id(
        "keep", incident.id, with_alerts=True, session=db_session
    )

    alerts_dtos = convert_db_alerts_to_dto_alerts(incident._alerts, session=db_session)
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

    db_session.expire_all()
    incident = get_incident_by_id(
        "keep", incident.id, with_alerts=True, session=db_session
    )

    assert incident.status == IncidentStatus.ACKNOWLEDGED.value
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident._alerts)
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

    db_session.expire_all()
    incident = get_incident_by_id(
        "keep", incident.id, with_alerts=True, session=db_session
    )

    assert incident.status == IncidentStatus.RESOLVED.value
    # All alerts are resolved as well
    alerts_dtos = convert_db_alerts_to_dto_alerts(incident._alerts, session=db_session)
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


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_incident_metadata(
    db_session, client, test_app, setup_stress_alerts_no_elastic
):
    severity_cycle = cycle([s.order for s in IncidentSeverity])
    status_cycle = cycle([s.value for s in IncidentStatus])
    sources_cycle = cycle(["keep", "keep-test", "keep-test-2"])
    services_cycle = cycle(["keep", "keep-test", "keep-test-2"])

    for i in range(50):
        severity = next(severity_cycle)
        status = next(status_cycle)
        service = next(services_cycle)
        source = next(sources_cycle)
        create_incident_from_dict(
            SINGLE_TENANT_UUID,
            {
                "user_generated_name": f"test-{i}",
                "user_summary": f"test-{i}",
                "is_confirmed": True,
                "assignee": f"assignee-{i % 5}",
                "severity": severity,
                "status": status,
                "sources": [source],
                "affected_services": [service],
            },
        )

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
        "fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "fp2",
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

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 0
    assert total_incident_alerts == 0

    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [fp1_alerts[0].fingerprint]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 1
    last_fp1_alert = (
        db_session.query(Alert.timestamp)
        .where(Alert.fingerprint == "fp1")
        .order_by(desc(Alert.timestamp))
        .first()
    )
    assert incident_alerts[0].timestamp == last_fp1_alert.timestamp
    assert total_incident_alerts == 1

    remove_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident.id, [fp1_alerts[0].fingerprint]
    )

    incident = get_incident_by_id(SINGLE_TENANT_UUID, incident.id)

    incident_alerts, total_incident_alerts = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=incident.id,
    )

    assert len(incident_alerts) == 0
    assert total_incident_alerts == 0


def test_merge_incidents(db_session, create_alert, setup_stress_alerts_no_elastic):
    incident_1 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Incident with info severity (destination)",
            "user_summary": "Incident with info severity (destination)",
        },
    )
    create_alert(
        "fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.INFO.value},
    )
    create_alert(
        "fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.INFO.value},
    )
    create_alert(
        "fp2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.INFO.value},
    )
    alerts_1 = db_session.query(Alert).all()
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_1.id, [a.fingerprint for a in alerts_1]
    )
    incident_2 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Incident with critical severity",
            "user_summary": "Incident with critical severity",
        },
    )
    create_alert(
        "fp20-0",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "fp20-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "fp20-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    alerts_2 = (
        db_session.query(Alert).filter(Alert.fingerprint.startswith("fp20")).all()
    )
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_2.id, [a.fingerprint for a in alerts_2]
    )
    incident_3 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Incident with warning severity",
            "user_summary": "Incident with warning severity",
        },
    )
    create_alert(
        "fp30-0",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.WARNING.value},
    )
    create_alert(
        "fp30-1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.INFO.value},
    )
    create_alert(
        "fp30-2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.WARNING.value},
    )
    alerts_3 = (
        db_session.query(Alert).filter(Alert.fingerprint.startswith("fp30")).all()
    )
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_3.id, [a.fingerprint for a in alerts_3]
    )

    # before merge
    incident_1 = get_incident_by_id(SINGLE_TENANT_UUID, incident_1.id)
    assert incident_1.severity == IncidentSeverity.INFO.order
    incident_2 = get_incident_by_id(SINGLE_TENANT_UUID, incident_2.id)
    assert incident_2.severity == IncidentSeverity.CRITICAL.order
    incident_3 = get_incident_by_id(SINGLE_TENANT_UUID, incident_3.id)
    assert incident_3.severity == IncidentSeverity.WARNING.order

    merge_incidents_to_id(
        SINGLE_TENANT_UUID,
        [incident_2.id, incident_3.id],
        incident_1.id,
        "test-user-email",
    )

    db_session.expire_all()

    incident_1 = get_incident_by_id(SINGLE_TENANT_UUID, incident_1.id, with_alerts=True)
    assert len(incident_1._alerts) == 8
    assert incident_1.severity == IncidentSeverity.CRITICAL.order

    incident_2 = get_incident_by_id(SINGLE_TENANT_UUID, incident_2.id, with_alerts=True)
    assert len(incident_2._alerts) == 0
    assert incident_2.status == IncidentStatus.MERGED.value
    assert incident_2.merged_into_incident_id == incident_1.id
    assert incident_2.merged_at is not None
    assert incident_2.merged_by == "test-user-email"

    incident_3 = get_incident_by_id(
        SINGLE_TENANT_UUID, incident_3.id, with_alerts=True, session=db_session
    )
    assert len(incident_3._alerts) == 0
    assert incident_3.status == IncidentStatus.MERGED.value
    assert incident_3.merged_into_incident_id == incident_1.id
    assert incident_3.merged_at is not None
    assert incident_3.merged_by == "test-user-email"


"""
@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_merge_incidents_app(
    db_session, client, test_app, setup_stress_alerts_no_elastic, create_alert
):
    incident_1 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Incident with info severity (destination)",
            "user_summary": "Incident with info severity (destination)",
        },
    )
    for i in range(50):
        create_alert(
            f"alert-1-{i}",
            AlertStatus.FIRING,
            datetime.utcnow(),
            {"severity": AlertSeverity.INFO.value},
        )
    alerts_1 = (
        db_session.query(Alert).filter(Alert.fingerprint.startswith("alert-1-")).all()
    )
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_1.id, [a.id for a in alerts_1]
    )
    incident_2 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Incident with critical severity",
            "user_summary": "Incident with critical severity",
        },
    )
    for i in range(50):
        create_alert(
            f"alert-2-{i}",
            AlertStatus.FIRING,
            datetime.utcnow(),
            {"severity": AlertSeverity.CRITICAL.value, "service": "second-service"},
        )
    alerts_2 = (
        db_session.query(Alert).filter(Alert.fingerprint.startswith("alert-2-")).all()
    )
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_2.id, [a.id for a in alerts_2]
    )
    incident_3 = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {"user_generated_name": "test-3", "user_summary": "test-3"},
    )
    alerts_3 = setup_stress_alerts_no_elastic(50)
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_3.id, [a.id for a in alerts_3]
    )
    empty_incident = create_incident_from_dict(
        SINGLE_TENANT_UUID, {"user_generated_name": "test-4", "user_summary": "test-4"}
    )

    incident_1_before_via_api = client.get(
        f"/incidents/{incident_1.id}", headers={"x-api-key": "some-key"}
    ).json()
    assert incident_1_before_via_api["severity"] == IncidentSeverity.INFO.value
    assert incident_1_before_via_api["alerts_count"] == 50
    assert "second-service" not in incident_1_before_via_api["services"]

    response = client.post(
        "/incidents/merge",
        headers={"x-api-key": "some-key"},
        json={
            "source_incident_ids": [
                str(incident_2.id),
                str(incident_3.id),
                str(empty_incident.id),
            ],
            "destination_incident_id": str(incident_1.id),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert set(result["merged_incident_ids"]) == {
        str(incident_2.id),
        str(incident_3.id),
    }
    assert result["skipped_incident_ids"] == [str(empty_incident.id)]
    assert result["failed_incident_ids"] == []

    incident_1_via_api = client.get(
        f"/incidents/{incident_1.id}", headers={"x-api-key": "some-key"}
    ).json()

    assert incident_1_via_api["id"] == str(incident_1.id)
    assert incident_1_via_api["severity"] == IncidentSeverity.CRITICAL.value
    assert incident_1_via_api["alerts_count"] == 150
    assert "second-service" in incident_1_via_api["services"]

    incident_2_via_api = client.get(
        f"/incidents/{incident_2.id}", headers={"x-api-key": "some-key"}
    ).json()
    assert incident_2_via_api["status"] == IncidentStatus.MERGED.value
    assert incident_2_via_api["merged_into_incident_id"] == str(incident_1.id)

    incident_3_via_api = client.get(
        f"/incidents/{incident_3.id}",
        headers={"x-api-key": "some-key"},
    ).json()
    assert incident_3_via_api["status"] == IncidentStatus.MERGED.value
    assert incident_3_via_api["merged_into_incident_id"] == str(incident_1.id)
"""
@pytest.mark.asyncio
async def test_split_incident(db_session, create_alert):
    # Create source incident with multiple alerts
    incident_source = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Source incident with mixed severity",
            "user_summary": "Source incident with mixed severity",
        },
    )
    
    # Create alerts with different severities
    create_alert(
        "fp1",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "fp2",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.WARNING.value},
    )
    create_alert(
        "fp3",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {"severity": AlertSeverity.INFO.value},
    )
    
    alerts = db_session.query(Alert).all()
    add_alerts_to_incident_by_incident_id(
        SINGLE_TENANT_UUID, incident_source.id, [a.fingerprint for a in alerts]
    )

    # Create destination incident
    incident_dest = create_incident_from_dict(
        SINGLE_TENANT_UUID,
        {
            "user_generated_name": "Destination incident",
            "user_summary": "Destination incident",
        },
    )

    # Verify initial state
    incident_source = get_incident_by_id(SINGLE_TENANT_UUID, incident_source.id, with_alerts=True)
    assert len(incident_source._alerts) == 3
    assert incident_source.severity == IncidentSeverity.CRITICAL.order

    incident_dest = get_incident_by_id(SINGLE_TENANT_UUID, incident_dest.id, with_alerts=True)
    assert len(incident_dest._alerts) == 0

    # Split the critical alert using IncidentBl
    critical_alert = next(a for a in alerts if a.event["severity"] == AlertSeverity.CRITICAL.value)
    incident_bl = IncidentBl(SINGLE_TENANT_UUID, db_session, pusher_client=None)
    
    # Move alert to destination incident
    await incident_bl.add_alerts_to_incident(
        incident_id=incident_dest.id,
        alert_fingerprints=[critical_alert.fingerprint]
    )
    
    # Remove alert from source incident
    incident_bl.delete_alerts_from_incident(
        incident_id=incident_source.id,
        alert_fingerprints=[critical_alert.fingerprint]
    )

    db_session.expire_all()

    # Verify final state
    incident_source = get_incident_by_id(SINGLE_TENANT_UUID, incident_source.id, with_alerts=True)
    assert len(incident_source._alerts) == 2
    assert incident_source.severity == IncidentSeverity.WARNING.order

    incident_dest = get_incident_by_id(SINGLE_TENANT_UUID, incident_dest.id, with_alerts=True)
    assert len(incident_dest._alerts) == 1
    assert incident_dest.severity == IncidentSeverity.CRITICAL.order
    assert incident_dest._alerts[0].fingerprint == critical_alert.fingerprint
    assert len(incident_dest._alerts) == 1
    assert incident_dest.severity == IncidentSeverity.CRITICAL.order
    assert incident_dest._alerts[0].fingerprint == critical_alert.fingerprint

# @pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
# def test_split_incident_app(db_session, client, test_app, create_alert):
#     create_alert(
#         "fp1",
#         AlertStatus.FIRING,
#         datetime.utcnow(),
#         {"severity": AlertSeverity.CRITICAL.value},
#     )
#     create_alert(
#         "fp2",
#         AlertStatus.FIRING,
#         datetime.utcnow(),
#         {"severity": AlertSeverity.CRITICAL.value},
#     )
#     create_alert(
#         "fp3",
#         AlertStatus.FIRING,
#         datetime.utcnow(),
#         {"severity": AlertSeverity.CRITICAL.value},
#     )
#     alerts = db_session.query(Alert).all()
#     incident_1 = create_incident_from_dict(
#         SINGLE_TENANT_UUID, {"user_generated_name": "test", "user_summary": "test"}
#     )
#     add_alerts_to_incident_by_incident_id(
#         SINGLE_TENANT_UUID, incident_1.id, [a.fingerprint for a in alerts]
#     )

#     incident_1 = get_incident_by_id(SINGLE_TENANT_UUID, incident_1.id, with_alerts=True)
#     assert len(incident_1._alerts) == 3

#     incident_2 = create_incident_from_dict(
#         SINGLE_TENANT_UUID, {"user_generated_name": "test", "user_summary": "test"}
#     )
#     incident_2 = get_incident_by_id(SINGLE_TENANT_UUID, incident_2.id, with_alerts=True)
#     assert len(incident_2._alerts) == 0

#     response = client.post(
#         f"/incidents/{str(incident_1.id)}/split",
#         headers={"x-api-key": "some-key"},
#         json={
#             "alert_fingerprints": [alerts[2].fingerprint],
#             "destination_incident_id": str(incident_2.id),
#         },
#     )

#     assert response.status_code == 200

#     incident_2 = get_incident_by_id(SINGLE_TENANT_UUID, incident_2.id, with_alerts=True)
#     assert incident_2._alerts[0].fingerprint == alerts[2].fingerprint

#     incident_1 = get_incident_by_id(SINGLE_TENANT_UUID, incident_1.id, with_alerts=True)
#     assert len(incident_1._alerts) == 2


def test_cross_tenant_exposure_issue_2768(db_session, create_alert):

    tenant_data = [
        Tenant(id="tenant_1", name="test-tenant-1", created_by="tests-1@keephq.dev"),
        Tenant(id="tenant_2", name="test-tenant-2", created_by="tests-2@keephq.dev"),
    ]
    db_session.add_all(tenant_data)
    db_session.commit()

    incident_tenant_1 = create_incident_from_dict(
        "tenant_1", {"user_generated_name": "test", "user_summary": "test"}
    )
    incident_tenant_2 = create_incident_from_dict(
        "tenant_2", {"user_generated_name": "test", "user_summary": "test"}
    )

    create_alert(
        "non-unique-fingerprint",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {},
        tenant_id="tenant_1",
    )

    create_alert(
        "non-unique-fingerprint",
        AlertStatus.FIRING,
        datetime.utcnow(),
        {},
        tenant_id="tenant_2",
    )

    alert_tenant_1 = (
        db_session.query(Alert).filter(Alert.tenant_id == "tenant_1").first()
    )
    alert_tenant_2 = (
        db_session.query(Alert).filter(Alert.tenant_id == "tenant_2").first()
    )

    add_alerts_to_incident_by_incident_id(
        "tenant_1", incident_tenant_1.id, [alert_tenant_1.fingerprint]
    )
    add_alerts_to_incident_by_incident_id(
        "tenant_2", incident_tenant_2.id, [alert_tenant_2.fingerprint]
    )

    incident_tenant_1 = get_incident_by_id("tenant_1", incident_tenant_1.id)
    incident_tenant_1_alerts, total_incident_tenant_1_alerts = (
        get_incident_alerts_by_incident_id(
            tenant_id="tenant_1",
            incident_id=incident_tenant_1.id,
        )
    )
    assert incident_tenant_1.alerts_count == 1
    assert total_incident_tenant_1_alerts == 1
    assert len(incident_tenant_1_alerts) == 1

    incident_tenant_2 = get_incident_by_id("tenant_2", incident_tenant_2.id)
    incident_tenant_2_alerts, total_incident_tenant_2_alerts = (
        get_incident_alerts_by_incident_id(
            tenant_id="tenant_2",
            incident_id=incident_tenant_2.id,
        )
    )
    assert incident_tenant_2.alerts_count == 1
    assert total_incident_tenant_2_alerts == 1
    assert len(incident_tenant_2_alerts) == 1
