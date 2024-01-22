"""
Shahar: We rewritten the Grouping logic, tests will be rewritten
        once we complete the new grouping logic
import datetime

import pytest

from keep.api.core.db import create_rule as create_rule_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.alert import Alert
from keep.rulesengine.rulesengine import RulesEngine


# Test that a simple rule works
@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
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


@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
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


@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
def test_another(db_session):
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


@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
def test_three_groups(db_session):
    alerts = [
        Alert(
            tenant_id=SINGLE_TENANT_UUID,
            provider_type="test",
            provider_id="test",
            event={"source": ["sentry"], "severity": "high"},
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


@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
def test_dict(db_session):
    # Insert alerts
    alert1 = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={
            "source": ["sentry"],
            "severity": "critical",
            "tags": {"some_attr": "123", "tag1": "badtag"},
        },
        fingerprint="test",
    )
    db_session.add_all([alert1])
    db_session.commit()
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="like-rule",
        definition={
            "sql": "((tags like :tags_1)",
            "params": {"tags_1": "%goodtag%", "service_1": "dev"},
        },
        timeframe=600,
        definition_cel='(tags.contains("sometag"))',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    # Run the rules engine
    results = rules_engine._run_rule(rules[0])
    assert results is None  # Expecting no alerts to match

    alert2 = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={
            "source": ["sentry"],
            "severity": "critical",
            "tags": {"some_attr": "123", "tag1": "goodtag"},
        },
        fingerprint="test",
    )
    db_session.add_all([alert2])
    db_session.commit()
    results = rules_engine._run_rule(rules[0])
    assert results and len(results) == 1
    # now check the alert
    alerts = list(results.values())[0]
    assert len(alerts) == 1
    assert alerts[0].event["tags"]["tag1"] == "goodtag"


@pytest.mark.parametrize("db_session", ["mysql", "sqlite"], indirect=["db_session"])
def test_dict_and_startswith(db_session):
    # Insert alerts
    alert1 = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={
            "source": ["sentry"],
            "severity": "critical",
            "tags": {"tag1": "sometag"},
        },
        fingerprint="test",
    )
    alert2 = Alert(
        tenant_id=SINGLE_TENANT_UUID,
        provider_type="test",
        provider_id="test",
        event={"source": ["grafana"], "severity": "high", "service": "dev-123"},
        fingerprint="test",
    )
    db_session.add_all([alert1, alert2])
    db_session.commit()

    # Create a rule using 'NOT' operator
    rules_engine = RulesEngine(tenant_id=SINGLE_TENANT_UUID)
    create_rule_db(
        tenant_id=SINGLE_TENANT_UUID,
        name="like-rule",
        definition={
            "sql": "((tags like :tags_1) and (service like :service_1))",
            "params": {"tags_1": "%sometag%", "service_1": "dev%"},
        },
        timeframe=600,
        definition_cel='(tags.contains("sometag")) && (service.startsWith("dev"))',
        created_by="test@keephq.dev",
    )
    rules = get_rules_db(SINGLE_TENANT_UUID)
    assert len(rules) == 1

    # Run the rules engine
    results = rules_engine._run_rule(rules[0])
    assert results and len(results) == 2


# TODO: add tests for all operators (IMPORTANT)
# TODO: add tests for every datatype e.g. source (list), severity (string), tags (dict), etc.
"""
