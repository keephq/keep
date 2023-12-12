import datetime

from conftest import db_session

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.alert import Alert
from keep.rulesengine.rulesengine import RulesEngine


# Test that a simple rule works
def test_sanity(db_session):
    # insert alerts
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["sentry"], "severity": "critical"},
            fingerprint="test",
        ),
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["grafana"], "severity": "critical"},
            fingerprint="test",
        ),
    ]

    db_session.add_all(alerts)
    db_session.commit()

    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1) and (source = :source_2 and severity = :severity_1))",
            "params": {
                "source_1": "sentry",
                "source_2": "grafana",
                "severity_1": "critical",
            },
        },
        timeframe=600,
        definition_cel='(source == "sentry") && (source == "grafana" && severity == "critical")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    rule = rules[0]
    # run the rules engine
    results = rules_engine._run_rule(rule)
    # check that there are results
    assert results is not None


def test_old_alerts(db_session):
    # insert alerts
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["sentry"], "severity": "critical"},
            fingerprint="test",
        ),
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["grafana"], "severity": "critical"},
            # 15 minutes ago so out of timeframe
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
            fingerprint="test",
        ),
    ]
    db_session.add_all(alerts)
    db_session.commit()

    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1) and (source = :source_2 and severity = :severity_1))",
            "params": {
                "source_1": "sentry",
                "source_2": "grafana",
                "severity_1": "critical",
            },
        },
        timeframe=600,
        definition_cel='(source == "sentry") && (source == "grafana" && severity == "critical")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    rule = rules[0]
    # run the rules engine
    results = rules_engine._run_rule(rule)
    # there should no results
    assert results is None


def test_another():
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["sentry"], "severity": "critical"},
            fingerprint="test",
        ),
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["grafana"], "severity": "critical"},
            # 15 minutes ago so out of timeframe
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
            fingerprint="test",
        ),
    ]
    db_session.add_all(alerts)
    db_session.commit()

    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1 and severity = :severity_1) and (source = :source_2 and severity = :severity_2))",
            "params": {
                "source_1": "sentry",
                "severity_1": "high",
                "source_2": "grafana",
                "severity_2": "critical",
            },
        },
        timeframe=600,
        definition_cel='(source == "sentry" && severity == "high") && (source == "grafana" && severity == "critical")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    rule = rules[0]
    # run the rules engine
    results = rules_engine._run_rule(rule)
    # there should no results
    assert results is None


def test_three_groups():
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["sentry"], "severity": "critical"},
            fingerprint="test",
        ),
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["grafana"], "severity": "critical"},
            # 15 minutes ago so out of timeframe
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
            fingerprint="test",
        ),
    ]
    db_session.add_all(alerts)
    db_session.commit()

    # create a simple rule
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    # simple rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1 and severity = :severity_1) and (source = :source_2 and severity = :severity_2) and (source = :source_3 and service = :service_1))",
            "params": {
                "source_1": "sentry",
                "severity_1": "high",
                "source_2": "grafana",
                "severity_2": "critical",
                "source_3": "elastic",
                "service_1": "db",
            },
        },
        timeframe=600,
        definition_cel='(source == "sentry" && severity == "high") && (source == "grafana" && severity == "critical") && (source == "elastic" && service == "db")',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    rule = rules[0]
    # run the rules engine
    results = rules_engine._run_rule(rule)
    # there should no results
    assert results is None

    # now insert another alert
    alert = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={"source": ["elastic"], "severity": "critical", "service": "db"},
        fingerprint="test",
    )
    db_session.add(alert)
    db_session.commit()
    # run the rules engine
    results = rules_engine._run_rule(rule)
    # there should be results
    assert results is not None


def test_find_relevant(db_session):
    # create first rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1 and severity = :severity_1) and (source = :source_2 and severity = :severity_2) and (source = :source_3 and service = :service_1))",
            "params": {
                "source_1": "sentry",
                "severity_1": "high",
                "source_2": "grafana",
                "severity_2": "critical",
                "source_3": "elastic",
                "service_1": "db",
            },
        },
        timeframe=600,
        definition_cel='(source == "sentry" && severity == "high") && (source == "grafana" && severity == "critical") && (source == "elastic" && service == "db")',
        created_by="test@keephq.dev",
    )
    # create seconds rule
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="test-rule",
        definition={
            "sql": "((source = :source_1 and severity = :severity_1) and (source = :source_2 and severity = :severity_2) and (source = :source_3 and service = :service_1))",
            "params": {
                "source_1": "sentry",
                "severity_1": "high",
                "source_2": "grafana",
                "severity_2": "critical",
                "source_3": "datadog",
                "service_1": "db",
            },
        },
        timeframe=600,
        definition_cel='(source == "datadog" && severity == "high") && (source == "grafana" && severity == "critical") && (source == "elastic" && service == "db")',
        created_by="test@keephq.dev",
    )
    # now let's create some event:
    # event = AlertDto()
