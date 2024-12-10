import datetime
import hashlib
import json
import os
import uuid
from time import sleep

import pytest

from keep.api.core.db import create_rule as create_rule_db, enrich_incidents_with_alerts
from keep.api.core.db import get_incident_alerts_by_incident_id, get_last_incidents, set_last_alert
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import (
    AlertDto,
    AlertSeverity,
    AlertStatus,
    IncidentSeverity,
    IncidentStatus,
)
from keep.api.models.db.alert import Alert, Incident
from keep.api.models.db.rule import ResolveOn, CreateIncidentOn
from keep.rulesengine.rulesengine import RulesEngine


@pytest.fixture(autouse=True)
def set_elastic_env():
    os.environ["ELASTIC_ENABLED"] = "false"


# Test that a simple rule works
def test_sanity(db_session):
    # insert alerts
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="grafana-test-alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2021-08-01T00:00:00Z",
        ),
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "sentry") || (source == "grafana" && severity == "critical")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alerts[0].dict(),
        fingerprint=alerts[0].fingerprint,
    )

    db_session.add(alert)
    db_session.commit()

    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)
    # check that there are results
    assert len(results) > 0


def test_sanity_2(db_session):
    # insert alerts
    alerts = [
        AlertDto(
            id="sentry-1",
            source=["sentry"],
            name="grafana-test-alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={"label_1": "a"},
        ),
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "sentry" && labels.label_1 == "a")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alerts[0].dict(),
        fingerprint=alerts[0].fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)
    # check that there are results
    assert len(results) > 0


def test_sanity_3(db_session):
    # insert alerts
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["sentry"],
            name="grafana-test-alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2021-08-01T00:00:00Z",
            tags={"tag_1": "tag1"},
            labels={"label_1": "a"},
        ),
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "sentry" && labels.label_1 == "a" && tags.tag_1.contains("tag"))',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alerts[0].dict(),
        fingerprint=alerts[0].fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)
    # check that there are results
    assert len(results) > 0


def test_sanity_4(db_session):
    # insert alerts
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["sentry"],
            name="grafana-test-alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2021-08-01T00:00:00Z",
            tags={"tag_1": "tag2"},
            labels={"label_1": "a"},
        ),
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "sentry" && labels.label_1 == "a" && tags.tag_1.contains("1234"))',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alerts[0].dict(),
        fingerprint=alerts[0].fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)
    # check that there are results
    assert results == []


def test_incident_attributes(db_session):
    # insert alerts
    alerts_dto = [
        AlertDto(
            id=str(uuid.uuid4()),
            source=["grafana"],
            name=f"grafana-test-alert-{i}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={"label_1": "a"},
        )
        for i in range(3)
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "grafana" && labels.label_1 == "a")',
        created_by="test@keephq.dev",
        create_on="any"
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint=alert.fingerprint,
            timestamp=alert.lastReceived,
        )
        for alert in alerts_dto
    ]
    db_session.add_all(alerts)
    db_session.commit()
    for alert in alerts:
        set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    for i, alert in enumerate(alerts_dto):
        alert.event_id = alerts[i].id
        results = rules_engine.run_rules([alert], session=db_session)
        # check that there are results
        assert results is not None
        assert len(results) == 1
        assert results[0].user_generated_name == "{}".format(rules[0].name)
        assert results[0].alerts_count == i + 1
        assert (
            results[0].last_seen_time.isoformat(timespec="milliseconds") + "Z"
            == alert.lastReceived
        )
        assert results[0].start_time == alerts[0].timestamp


def test_incident_severity(db_session):
    alerts_dto = [
        AlertDto(
            id=str(uuid.uuid4()),
            source=["grafana"],
            name=f"grafana-test-alert-{i}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={"label_1": "a"},
        )
        for i in range(3)
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(source == "grafana" && labels.label_1 == "a")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1
    # add the alert to the db:
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint=alert.fingerprint,
            timestamp=alert.lastReceived,
        )
        for alert in alerts_dto
    ]
    db_session.add_all(alerts)
    db_session.commit()
    for alert in alerts:
        set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    for i, alert in enumerate(alerts_dto):
        alert.event_id = alerts[i].id

    results = rules_engine.run_rules(alerts_dto, session=db_session)
    # check that there are results
    assert results is not None
    assert len(results) == 1
    assert results[0].user_generated_name == "{}".format(rules[0].name)
    assert results[0].alerts_count == 3
    assert results[0].severity.value == IncidentSeverity.INFO.value


def test_incident_resolution_on_all(db_session, create_alert):

    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(severity == "critical")',
        created_by="test@keephq.dev",
        require_approve=False,
        resolve_on=ResolveOn.ALL.value,
    )

    incidents, total_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=1,
    )
    assert total_count == 0

    create_alert(
        "Something went wrong",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "Something went wrong again",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]
    assert incident.status == IncidentStatus.FIRING.value

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    assert alert_count == 2

    # Same fingerprint
    create_alert(
        "Something went wrong",
        AlertStatus.RESOLVED,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    # Still 2 alerts, since 2 unique fingerprints
    assert alert_count == 2
    assert incident.status == IncidentStatus.FIRING.value

    create_alert(
        "Something went wrong again",
        AlertStatus.RESOLVED,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    assert alert_count == 2
    assert incident.status == IncidentStatus.RESOLVED.value


@pytest.mark.parametrize(
    "direction,second_fire_order",
    [(ResolveOn.FIRST.value, ("fp2", "fp1")), (ResolveOn.LAST.value, ("fp2", "fp1"))],
)
def test_incident_resolution_on_edge(
    db_session, create_alert, direction, second_fire_order
):

    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(severity == "critical")',
        created_by="test@keephq.dev",
        require_approve=False,
        resolve_on=direction,
    )

    incidents, total_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=1,
    )
    assert total_count == 0

    create_alert(
        "fp1",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )
    create_alert(
        "fp2",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]
    assert incident.status == IncidentStatus.FIRING.value

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    assert alert_count == 2

    fp1, fp2 = second_fire_order

    create_alert(
        fp1,
        AlertStatus.RESOLVED,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    assert alert_count == 2
    assert incident.status == IncidentStatus.FIRING.value

    create_alert(
        fp2,
        AlertStatus.RESOLVED,
        datetime.datetime.utcnow(),
        {"severity": AlertSeverity.CRITICAL.value},
    )

    incidents, incidents_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert incidents_count == 1

    incident = incidents[0]

    db_alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        limit=10,
        offset=0,
    )
    assert alert_count == 2
    assert incident.status == IncidentStatus.RESOLVED.value


def test_rule_multiple_alerts(db_session, create_alert):

    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='(severity == "critical") || (severity == "high")',
        created_by="test@keephq.dev",
        create_on=CreateIncidentOn.ALL.value,
    )

    create_alert(
        "Critical Alert",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "severity": AlertSeverity.CRITICAL.value,
        },
    )

    # No incident yet
    assert db_session.query(Incident).filter(Incident.is_confirmed == True).count() == 0
    # But candidate is there
    assert db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1
    incident = db_session.query(Incident).first()
    alert_1 = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

    enrich_incidents_with_alerts(SINGLE_TENANT_UUID, [incident], db_session)

    assert incident.alerts_count == 1
    assert len(incident.alerts) == 1
    assert incident.alerts[0].id == alert_1.id

    create_alert(
        "Critical Alert 2",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "severity": AlertSeverity.CRITICAL.value,
        },
    )

    db_session.refresh(incident)
    alert_2 = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()

    # Still no incident yet
    assert db_session.query(Incident).filter(Incident.is_confirmed == True).count() == 0
    # And still one candidate is there
    assert db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1

    enrich_incidents_with_alerts(SINGLE_TENANT_UUID, [incident], db_session)

    assert incident.alerts_count == 2
    assert len(incident.alerts) == 2
    assert incident.alerts[0].id == alert_1.id
    assert incident.alerts[1].id == alert_2.id

    create_alert(
        "High Alert",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "severity": AlertSeverity.HIGH.value,
        },
    )

    alert_3 = db_session.query(Alert).order_by(Alert.timestamp.desc()).first()
    enrich_incidents_with_alerts(SINGLE_TENANT_UUID, [incident], db_session)

    # And incident was official started
    assert db_session.query(Incident).filter(Incident.is_confirmed == True).count() == 1

    db_session.refresh(incident)
    assert incident.alerts_count == 3

    alerts, alert_count = get_incident_alerts_by_incident_id(
        tenant_id=SINGLE_TENANT_UUID,
        incident_id=str(incident.id),
        session=db_session,
    )
    assert alert_count == 3
    assert len(alerts) == 3

    fingerprints = [a.fingerprint for a in alerts]

    assert alert_1.fingerprint in fingerprints
    assert alert_2.fingerprint in fingerprints
    assert alert_3.fingerprint in fingerprints


def test_rule_event_groups_expires(db_session, create_alert):

    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=1,
        timeunit="seconds",
        definition_cel='(severity == "critical") || (severity == "high")',
        created_by="test@keephq.dev",
        create_on=CreateIncidentOn.ALL.value,
    )

    create_alert(
        "Critical Alert",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "severity": AlertSeverity.CRITICAL.value,
        },
    )

    # Still no incident yet
    assert db_session.query(Incident).filter(Incident.is_confirmed == True).count() == 0
    # And still one candidate is there
    assert db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1

    sleep(1)

    create_alert(
        "High Alert",
        AlertStatus.FIRING,
        datetime.datetime.utcnow(),
        {
            "severity": AlertSeverity.HIGH.value,
        },
    )

    # Still no incident yet
    assert db_session.query(Incident).filter(Incident.is_confirmed == True).count() == 0
    # And now two candidates is there
    assert db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 2



# Next steps:
#   - test that alerts in the same group are being updated correctly
#   - test group are being updated correctly
#   - test that alerts in different groups are being updated correctly
#   - test timeframes - new group is created
#   - test timeframes - old group is not updated
#   - test more matchers (CEL's)
#       - three groups
#       - one group
#       - more CEL operators
#   - test group attributes - severity and status
#   - test group attributes - labels
#   - test that if more than one rule matches, the alert is being updated correctly
#   - test that if more than one rule matches, the alert is being updated correctly - different group
