from datetime import datetime

import pytz
from sqlalchemy import func

from keep.api.core.db import (
    add_alerts_to_incident_by_incident_id,
    create_incident_from_dict,
    get_alerts_data_for_incident,
    get_incident_by_id,
    remove_alerts_to_incident_by_incident_id,
)
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import Alert


def test_get_alerts_data_for_incident(db_session, setup_stress_alerts_no_elastic):
    alerts = setup_stress_alerts_no_elastic(100)
    assert 100 == db_session.query(func.count(Alert.id)).scalar()

    data = get_alerts_data_for_incident([a.id for a in alerts])
    assert data["sources"] == set(["source_{}".format(i) for i in range(10)])
    assert data["services"] == set(["service_{}".format(i) for i in range(10)])
    assert data["count"] == 100


def test_add_remove_alert_to_incidents(db_session, setup_stress_alerts_no_elastic):
    alerts = setup_stress_alerts_no_elastic(100)
    incident = create_incident_from_dict("keep", {"name": "test", "description": "test"})

    assert len(incident.alerts) == 0

    add_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [a.id for a in alerts]
    )

    incident = get_incident_by_id("keep", incident.id)

    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(10)])
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(10)])

    service_0 = (
        db_session.query(Alert.id)
        .filter(
            func.json_extract(Alert.event, "$.service") == "service_0"
        )
        .all()
    )

    remove_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [service_0[0].id, ]
    )

    incident = get_incident_by_id("keep", incident.id)

    assert len(incident.alerts) == 99
    assert "service_0" in incident.affected_services
    assert len(incident.affected_services) == 10
    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(10)])

    remove_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [a.id for a in service_0]
    )

    incident = get_incident_by_id("keep", incident.id)

    assert len(incident.alerts) == 90
    assert "service_0" not in incident.affected_services
    assert len(incident.affected_services) == 9
    assert sorted(incident.affected_services) == sorted(["service_{}".format(i) for i in range(1, 10)])

    source_1 = (
        db_session.query(Alert.id)
        .filter(
            func.json_extract(Alert.event, "$.source") == '["source_1"]'
        )
        .all()
    )

    remove_alerts_to_incident_by_incident_id(
        "keep",
        incident.id,
        [source_1[0].id, ]
    )

    incident = get_incident_by_id("keep", incident.id)

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

    incident = get_incident_by_id("keep", incident.id)

    assert len(incident.sources) == 8
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(2, 10)])


def test_remove_alert_with_multiple_source_from_incident(db_session, create_alert):
    incident = create_incident_from_dict("keep", {"name": "test", "description": "test"})

    timestamp = datetime.now(tz=pytz.utc)
    alert1 = create_alert("fp1", AlertStatus.FIRING, timestamp, {"source": ["source_0", "source_1"]})
    alert2 = create_alert("fp2", AlertStatus.FIRING, timestamp, {"source": ["source_1"]})

    add_alerts_to_incident_by_incident_id("keep", incident.id, [alert1.id, alert2.id])

    incident = get_incident_by_id("keep", incident.id)

    assert len(incident.alerts) == 2
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(2)])

    remove_alerts_to_incident_by_incident_id("keep", incident.id, [alert2.id])

    incident = get_incident_by_id("keep", incident.id)

    assert len(incident.alerts) == 1
    assert sorted(incident.sources) == sorted(["source_{}".format(i) for i in range(2)])
