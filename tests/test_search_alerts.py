import datetime
import uuid

import pytest

from keep.api.core.db import enrich_alert, get_alerts_with_filters
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import Alert
from keep.api.routes.alerts import convert_db_alerts_to_dto_alerts
from keep.rulesengine.rulesengine import RulesEngine

# Shahar: If you are struggling - you can play with https://playcel.undistro.io/ to see how the CEL expressions work


@pytest.fixture
def setup_alerts(db_session, request):
    alert_details = request.param.get("alert_details")
    alerts = []
    for i, detail in enumerate(alert_details):
        detail["fingerprint"] = f"test-{i}"
        alerts.append(
            Alert(
                tenant_id=SINGLE_TENANT_UUID,
                provider_type="test",
                provider_id="test",
                event=_create_valid_event(detail),
                fingerprint=detail["fingerprint"],
            )
        )
    db_session.add_all(alerts)
    db_session.commit()


def _create_valid_event(d):
    event = {
        "id": str(uuid.uuid4()),
        "name": "some-test-event",
        "lastReceived": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
    }
    event.update(d)
    return event


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '(source == "sentry")'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity2(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '(source == "sentry" || source == "grafana")'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 2


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity_3(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '!(source == "sentry" || source == "grafana")'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 0


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity_4(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    # mark alerts as dismissed
    enrich_alert(
        SINGLE_TENANT_UUID,
        fingerprint="test-1",
        enrichments={"dismissed": True},
    )
    search_query = '((source == "sentry" || source == "grafana") && !dismissed)'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_value",
                        "another_label": "another_value",
                    },
                },
                {
                    "source": ["datadog"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_value",
                        "another_label": "another_value",
                    },
                },
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity_5(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '(labels.some_label == "some_value")'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 3
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 2
    assert filtered_alerts[0].fingerprint == "test-1"
    assert filtered_alerts[1].fingerprint == "test-2"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_bla_value",
                        "another_label": "another_value",
                    },
                },
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {"some_label": "bla", "another_label": "another_value"},
                },
                {
                    "source": ["datadog"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_value",
                        "another_label": "another_value",
                    },
                },
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity_6(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '(labels.some_label.contains("bla"))'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 4
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 2
    assert filtered_alerts[0].fingerprint == "test-2"
    assert filtered_alerts[1].fingerprint == "test-1"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_bla_value",
                        "another_label": "another_value",
                    },
                },
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {"some_label": "bla", "another_label": "another_value"},
                    "some_list": ["a", "b"],
                },
                {
                    "source": ["datadog"],
                    "severity": "critical",
                    "labels": {
                        "some_label": "some_value",
                        "another_label": "another_value",
                    },
                },
            ]
        }
    ],
    indirect=True,
)
def test_search_sanity_7(db_session, setup_alerts):
    timeframe_in_days = 3600 / 86400  # last hour
    search_query = '(labels.some_label.contains("bla") && "b" in some_list)'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=timeframe_in_days
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 4
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].fingerprint == "test-2"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["application"], "count": 10},
                {"source": ["database"], "count": 5},
            ]
        }
    ],
    indirect=True,
)
def test_greater_than(db_session, setup_alerts):
    search_query = "(count > 6)"
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].count == 10


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["sentry"], "severity": "critical"},
                {"source": ["grafana"], "severity": "warning"},
            ]
        }
    ],
    indirect=True,
)
def test_not_equal(db_session, setup_alerts):
    search_query = '(severity != "critical")'
    # Your existing test workflow follows here
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].severity == "warning"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["system"], "active": True},
                {"source": ["backup"], "active": False},
            ]
        }
    ],
    indirect=True,
)
def test_logical_not(db_session, setup_alerts):
    search_query = "(!active)"
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].active == False


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["ui"], "user": "admin"},
                {"source": ["backend"], "user": "developer"},
            ]
        }
    ],
    indirect=True,
)
def test_in_operator(db_session, setup_alerts):
    search_query = '(user in ["admin", "guest"])'
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].user == "admin"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["frontend"], "path": "/home"},
                {"source": ["backend"], "path": "/api/data"},
            ]
        }
    ],
    indirect=True,
)
def test_starts_with(db_session, setup_alerts):
    search_query = '(path.startsWith("/api"))'
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].path == "/api/data"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["task"], "assigned": None},
                {"source": ["job"], "assigned": "user123"},
            ]
        }
    ],
    indirect=True,
)
def test_null_handling(db_session, setup_alerts):
    search_query = "(assigned == null)"
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].assigned == None


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["monitoring"], "tags": ["urgent", "review"]},
                {"source": ["logging"], "tags": ["ignore"]},
            ]
        }
    ],
    indirect=True,
)
def test_in_with_list(db_session, setup_alerts):
    search_query = '("urgent" in tags)'
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].tags == ["urgent", "review"]


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {
                    "source": ["application"],
                    "metrics": {
                        "requests": 100,
                        "errors": {"timeout": 10, "server": 5},
                    },
                },
                {
                    "source": ["database"],
                    "metrics": {
                        "requests": 150,
                        "errors": {"timeout": 20, "server": 0},
                    },
                },
            ]
        }
    ],
    indirect=True,
)
def test_complex_nested_queries(db_session, setup_alerts):
    search_query = "((metrics.requests > 100) && (metrics.errors.timeout > 15 || metrics.errors.server < 1))"
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].source == ["database"]


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["api"], "endpoint": "/user/create"},
                {"source": ["api"], "endpoint": "/auth/login?redirect=/home"},
            ]
        }
    ],
    indirect=True,
)
def test_special_characters_in_strings(db_session, setup_alerts):
    search_query = '(endpoint == "/auth/login?redirect=/home")'
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].endpoint == "/auth/login?redirect=/home"


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {
                    "source": ["frontend"],
                    "responseTimes": [120, 250, 180],
                    "status": AlertStatus.RESOLVED.value,
                },
                {
                    "source": ["backend"],
                    "responseTimes": [300, 400, 500],
                    "status": AlertStatus.FIRING.value,
                },
            ]
        }
    ],
    indirect=True,
)
def test_high_complexity_queries(db_session, setup_alerts):
    search_query = (
        '((responseTimes[0] < 200 || responseTimes[1] > 200) && status == "resolved")'
    )
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 2
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].source == ["frontend"]


# Actually found a big in celpy comparing list to None
@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {"source": ["job"], "queue": []},
                {"source": ["task"], "queue": ["urgent", "high"]},
                {"source": ["process"], "queue": None},
            ]
        }
    ],
    indirect=True,
)
def test_empty_and_null_fields(db_session, setup_alerts):
    search_query = "(queue == [])"
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    assert len(alerts_dto) == 3
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].source == ["job"]
    search_query = "(queue == null)"
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].source == ["process"]
    # search_query = '(queue != null)'
    # filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    # assert len(filtered_alerts) == 2


"""
def test_nonexist_label(db_session):
    pass
"""


"""
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
"""
