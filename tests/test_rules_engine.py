import datetime
import os
import uuid
from time import sleep

import pytest

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.db import (
    enrich_incidents_with_alerts,
    get_incident_alerts_by_incident_id,
    get_last_incidents,
)
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.db import set_last_alert
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import (
    AlertDto,
    AlertSeverity,
    AlertStatus,
    IncidentSeverity,
    IncidentStatus,
)
from keep.api.models.db.alert import Alert, Incident
from keep.api.models.db.rule import CreateIncidentOn, ResolveOn
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
        create_on="any",
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
    assert (
        db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1
    )
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
    assert (
        db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1
    )

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
    assert (
        db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 1
    )

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
    assert (
        db_session.query(Incident).filter(Incident.is_confirmed == False).count() == 2
    )


def test_at_sign(db_session):
    # insert alerts
    event = {
        "@timestamp": "abc",
        "#$": "abc",
        "!what": "abc",
        "bla": {
            "@timestamp": "abc",
        },
    }
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="grafana-test-alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived="2021-08-01T00:00:00Z",
            **event,
        ),
    ]
    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    cel = '(source == "sentry") || (source == "grafana" && severity == "critical")'
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",  # we don't use it anymore
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel=cel,
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

    alerts = rules_engine.filter_alerts(alerts, cel)
    assert len(alerts) == 1
    assert alerts[0].id == "grafana-1"


def test_incident_name_template_simple(db_session):
    # insert alerts with specific host and service
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="Test alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={"host": "web-server-1", "service": "nginx"},
        ),
    ]

    # create rule with templated name
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "N/A",
            "params": {},
        },
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Issue on {{ alert.labels.host }} with {{ alert.labels.service }}",
    )

    # add the alert to db
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

    # run rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)

    # verify results
    assert len(results) == 1
    assert results[0].user_generated_name == "Issue on web-server-1 with nginx"


def test_incident_name_template_nested(db_session):
    # test with nested alert properties
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="Complex alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={
                "environment": "production",
                "metadata": {"region": "us-east", "datacenter": "dc1"},
            },
        ),
    ]

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Alert in {{ alert.labels.environment }} ({{ alert.labels.metadata.region }})",
    )

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

    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)

    assert len(results) == 1
    assert results[0].user_generated_name == "Alert in production (us-east)"


def test_incident_name_template_fallback(db_session):
    # test fallback when template variables don't exist
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="Missing fields alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={},  # empty labels
        ),
    ]

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Issue on {{ alert.labels.non_existent_field }}",
    )

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

    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)

    assert len(results) == 1
    # Should fallback to rule name if template rendering fails
    assert results[0].user_generated_name == "Issue on N/A"


def test_incident_name_template_multiple_alerts(db_session):
    """Test that incident name updates correctly as new alerts are added"""
    # First alert
    alert1 = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="First alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-1", "service": "nginx"},
    )

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Issues on hosts: {{ alert.labels.host }}",
    )

    # Add first alert
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert1.dict(),
        fingerprint=alert1.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert1.event_id = alert.id
    results = rules_engine.run_rules([alert1], session=db_session)
    assert len(results) == 1
    assert results[0].user_generated_name == "Issues on hosts: web-1"

    # Second alert
    alert2 = AlertDto(
        id="grafana-2",
        source=["grafana"],
        name="Second alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-2", "service": "nginx"},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert2.dict(),
        fingerprint=alert2.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert2.event_id = alert.id
    results = rules_engine.run_rules([alert2], session=db_session)
    assert len(results) == 1
    assert results[0].user_generated_name == "Issues on hosts: web-1,web-2"


def test_incident_name_template_partial_fields(db_session):
    """Test template rendering when some fields exist and others don't"""
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="Partial fields alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={"host": "web-1"},  # service is missing
        ),
    ]

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Host {{ alert.labels.host }} Service {{ alert.labels.service }}",
    )

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

    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)

    assert len(results) == 1
    # Service should be empty or replaced with placeholder
    assert results[0].user_generated_name == "Host web-1 Service N/A"


def test_incident_name_template_complex_fields(db_session):
    """Test template rendering with complex field types like lists and dictionaries"""
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana", "prometheus"],  # List
            name="Complex fields alert",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            labels={  # Dictionary
                "hosts": ["web-1", "web-2"],
                "services": {"primary": "nginx", "secondary": "mysql"},
            },
        ),
    ]

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source.contains("grafana")',
        created_by="test@keephq.dev",
        incident_name_template=(
            "Sources: {{ alert.source }}, "
            "Hosts: {{ alert.labels.hosts }}, "
            "Primary service: {{ alert.labels.services.primary }}"
        ),
    )

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

    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts, session=db_session)

    assert len(results) == 1
    assert results[0].user_generated_name == (
        "Sources: ['grafana', 'prometheus'], "
        "Hosts: ['web-1', 'web-2'], "
        "Primary service: nginx"
    )


def test_incident_name_template_different_alerts_same_incident(db_session):
    """Test name template with different alerts in same incident"""
    # First alert with some fields
    alert1 = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="First alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-1", "service": "nginx"},
    )

    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Affected services: {{ alert.labels.service }}",
    )

    # Add first alert
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert1.dict(),
        fingerprint=alert1.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert1.event_id = alert.id
    results = rules_engine.run_rules([alert1], session=db_session)
    assert results[0].user_generated_name == "Affected services: nginx"

    # Second alert with different fields
    alert2 = AlertDto(
        id="grafana-2",
        source=["grafana"],
        name="Second alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-2", "service": "mysql"},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert2.dict(),
        fingerprint=alert2.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert2.event_id = alert.id
    results = rules_engine.run_rules([alert2], session=db_session)
    assert results[0].user_generated_name == "Affected services: nginx,mysql"


def test_multiple_incidents_name_template(db_session):
    """Test name templates when multiple incidents are created from same rule"""
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)

    # Create rule that will generate separate incidents based on host
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Issues on {{ alert.labels.host }}: {{ alert.labels.services }}",
        grouping_criteria=["labels.host"],  # Create separate incidents per host
    )

    # First alert - will create first incident
    alert1 = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="First alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-1", "services": ["nginx"]},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert1.dict(),
        fingerprint=alert1.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert1.event_id = alert.id
    results = rules_engine.run_rules([alert1], session=db_session)
    assert len(results) == 1
    incident1 = results[0]
    assert incident1.user_generated_name == "Issues on web-1: ['nginx']"

    # Second alert - will create second incident (different host)
    alert2 = AlertDto(
        id="grafana-2",
        source=["grafana"],
        name="Second alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-2", "services": ["mysql", "redis"]},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert2.dict(),
        fingerprint=alert2.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert2.event_id = alert.id
    results = rules_engine.run_rules([alert2], session=db_session)
    assert len(results) == 1
    incident2 = results[0]
    assert incident2.user_generated_name == "Issues on web-2: ['mysql', 'redis']"
    assert incident1.id != incident2.id  # Verify these are different incidents

    # Third alert - should be added to first incident (same host as alert1)
    alert3 = AlertDto(
        id="grafana-3",
        source=["grafana"],
        name="Third alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-1", "services": ["postgresql"]},  # Same host as alert1
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert3.dict(),
        fingerprint=alert3.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert3.event_id = alert.id
    results = rules_engine.run_rules([alert3], session=db_session)
    assert len(results) == 1
    updated_incident1 = results[0]

    # Verify incidents
    assert updated_incident1.id == incident1.id  # Same incident as first alert
    assert (
        updated_incident1.user_generated_name
        == "Issues on web-1: ['nginx'],['postgresql']"
    )

    # Get all incidents and verify their current state
    incidents, total_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert total_count == 2  # Should have two incidents total

    # Find each incident and verify its name
    for incident in incidents:
        if incident.id == incident1.id:
            assert (
                incident.user_generated_name
                == "Issues on web-1: ['nginx'],['postgresql']"
            )
        elif incident.id == incident2.id:
            assert incident.user_generated_name == "Issues on web-2: ['mysql', 'redis']"
        else:
            assert False, "Unexpected incident found"


def test_multiple_incidents_name_template_with_updates(db_session):
    """Test name templates when alerts are updated in multiple incidents"""
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)

    # Create rule that will generate separate incidents based on service
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana"',
        created_by="test@keephq.dev",
        incident_name_template="Service {{ alert.labels.service }} issues - Hosts: {{ alert.labels.host }}",
        grouping_criteria=["labels.service"],
    )

    # First alert - nginx incident
    alert1 = AlertDto(
        id="grafana-1",
        source=["grafana"],
        name="First alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-1", "service": "nginx"},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert1.dict(),
        fingerprint=alert1.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert1.event_id = alert.id
    results = rules_engine.run_rules([alert1], session=db_session)
    nginx_incident = results[0]
    assert nginx_incident.user_generated_name == "Service nginx issues - Hosts: web-1"

    # Second alert - mysql incident
    alert2 = AlertDto(
        id="grafana-2",
        source=["grafana"],
        name="Second alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "db-1", "service": "mysql"},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert2.dict(),
        fingerprint=alert2.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert2.event_id = alert.id
    results = rules_engine.run_rules([alert2], session=db_session)
    mysql_incident = results[0]

    # Third alert - updates nginx incident
    alert3 = AlertDto(
        id="grafana-3",
        source=["grafana"],
        name="Third alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "web-2", "service": "nginx"},  # Same service as alert1
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert3.dict(),
        fingerprint=alert3.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert3.event_id = alert.id
    results = rules_engine.run_rules([alert3], session=db_session)

    # Fourth alert - updates mysql incident
    alert4 = AlertDto(
        id="grafana-4",
        source=["grafana"],
        name="Fourth alert",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.datetime.now().isoformat(),
        labels={"host": "db-2", "service": "mysql"},
    )

    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event=alert4.dict(),
        fingerprint=alert4.fingerprint,
    )
    db_session.add(alert)
    db_session.commit()
    set_last_alert(SINGLE_TENANT_UUID, alert, db_session)

    alert4.event_id = alert.id
    results = rules_engine.run_rules([alert4], session=db_session)

    # Verify final state
    incidents, total_count = get_last_incidents(
        tenant_id=SINGLE_TENANT_UUID,
        is_confirmed=True,
        limit=10,
        offset=0,
    )

    assert total_count == 2

    # Verify names of both incidents
    for incident in incidents:
        if incident.id == nginx_incident.id:
            assert (
                incident.user_generated_name
                == "Service nginx issues - Hosts: web-1,web-2"
            )
        elif incident.id == mysql_incident.id:
            assert (
                incident.user_generated_name
                == "Service mysql issues - Hosts: db-1,db-2"
            )
        else:
            assert False, "Unexpected incident found"


def test_incident_created_only_for_firing_alerts(db_session):
    # Insert alerts with different statuses
    alerts = [
        AlertDto(
            id="grafana-1",
            source=["grafana"],
            name="Non-firing alert",
            status=AlertStatus.RESOLVED,  # Non-firing status
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            fingerprint="Non-firing alert"
        ),
        AlertDto(
            id="grafana-2",
            source=["grafana"],
            name="Firing alert",
            status=AlertStatus.FIRING,  # Firing status
            severity=AlertSeverity.CRITICAL,
            lastReceived=datetime.datetime.now().isoformat(),
            fingerprint="Firing alert"
        ),
    ]

    # Create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={"sql": "N/A", "params": {}},
        timeframe=600,
        timeunit="seconds",
        definition_cel='source == "grafana" && severity == "critical"',
        created_by="test@keephq.dev",
    )

    # Add the alerts to the database
    alert_entities = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event=alert.dict(),
            fingerprint=alert.fingerprint,
        )
        for alert in alerts
    ]
    db_session.add_all(alert_entities)
    db_session.commit()
    for alert_entity in alert_entities:
        set_last_alert(SINGLE_TENANT_UUID, alert_entity, db_session)

    for i, alert in enumerate(alerts):
        alert.event_id = alert_entities[i].id

    # Run the rules engine
    results = rules_engine.run_rules(alerts, session=db_session)

    # Verify that only one incident is created for the firing alert
    assert results is not None
    assert len(results) == 1
    assert results[0].alerts_count == 1
    assert results[0].status == IncidentStatus.FIRING
    assert results[0].alerts[0].name == "Firing alert"

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
