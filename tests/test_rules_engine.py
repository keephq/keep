import datetime
import hashlib
import json
import os
import time
import uuid

import pytest

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus, IncidentSeverity
from keep.api.models.db.alert import Alert
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
        fingerprint="test",
    )
    db_session.add(alert)
    db_session.commit()
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts)
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
        fingerprint="test",
    )
    db_session.add(alert)
    db_session.commit()
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts)
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
        fingerprint="test",
    )
    db_session.add(alert)
    db_session.commit()
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts)
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
        fingerprint="test",
    )
    db_session.add(alert)
    db_session.commit()
    # run the rules engine
    alerts[0].event_id = alert.id
    results = rules_engine.run_rules(alerts)
    # check that there are results
    assert results == []


def test_incident_attributes(db_session):
    # insert alerts
    alerts_dto = [
        AlertDto(
            id=str(uuid.uuid4()),
            source=["grafana"],
            name="grafana-test-alert",
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
            fingerprint=hashlib.sha256(json.dumps(alert.dict()).encode()).hexdigest(),
            timestamp=alert.lastReceived,
        )
        for alert in alerts_dto
    ]
    db_session.add_all(alerts)
    db_session.commit()

    for i, alert in enumerate(alerts_dto):
        alert.event_id = alerts[i].id
        results = rules_engine.run_rules([alert])
        # check that there are results
        assert results is not None
        assert len(results) == 1
        assert results[0].user_generated_name == "Incident generated by rule {}".format(rules[0].name)
        assert results[0].alerts_count == i + 1
        assert results[0].last_seen_time.isoformat(timespec='milliseconds')+"Z" == alert.lastReceived
        assert results[0].start_time == alerts[0].timestamp


def test_incident_severity(db_session):
    alerts_dto = [
        AlertDto(
            id=str(uuid.uuid4()),
            source=["grafana"],
            name="grafana-test-alert",
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
            fingerprint=hashlib.sha256(json.dumps(alert.dict()).encode()).hexdigest(),
            timestamp=alert.lastReceived,
        )
        for alert in alerts_dto
    ]
    db_session.add_all(alerts)
    db_session.commit()

    for i, alert in enumerate(alerts_dto):
        alert.event_id = alerts[i].id

    results = rules_engine.run_rules(alerts_dto)
    # check that there are results
    assert results is not None
    assert len(results) == 1
    assert results[0].user_generated_name == "Incident generated by rule {}".format(rules[0].name)
    assert results[0].alerts_count == 3
    assert results[0].severity.value == IncidentSeverity.INFO.value



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
