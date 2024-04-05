import datetime
import random
import time
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


@pytest.fixture
def setup_stress_alerts(db_session, request):
    num_alerts = request.param.get(
        "num_alerts", 1000
    )  # Default to 1000 alerts if not specified
    alert_details = [
        {
            "source": [
                "source_{}".format(i % 10)
            ],  # Cycle through 10 different sources
            "severity": random.choice(
                ["info", "warning", "critical"]
            ),  # Alternate between 'critical' and 'warning'
        }
        for i in range(num_alerts)
    ]
    alerts = []
    for i, detail in enumerate(alert_details):
        alerts.append(
            Alert(
                tenant_id=SINGLE_TENANT_UUID,
                provider_type="test",
                provider_id="test_{}".format(
                    i % 5
                ),  # Cycle through 5 different provider_ids
                event=_create_valid_event(detail),
                fingerprint="fingerprint_{}".format(i),
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
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {"some_label": "bla", "another_label": "another_value"},
                    "some_list": ["a", "b"],
                },
                {
                    "source": ["grafana"],
                    "severity": "critical",
                    "labels": {"some_label": "bla", "another_label": "another_value"},
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
    # assert len(alerts_dto) == 4
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].fingerprint == "test-0"


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
# https://github.com/cloud-custodian/cel-python/issues/59
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
    # bug - https://github.com/cloud-custodian/cel-python/issues/59
    # search_query = '(queue != null)'
    # filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    # assert len(filtered_alerts) == 2


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {
                    "source": ["dynamic"],
                    "event": {
                        "@type": "type.googleapis.com/google.protobuf.Value",
                        "value": {
                            "listValue": {
                                "values": [
                                    {"numberValue": 100},
                                    {"stringValue": "test"},
                                    {"boolValue": True},
                                ]
                            }
                        },
                    },
                }
            ]
        }
    ],
    indirect=True,
)
def test_complex_dynamic_conversions(db_session, setup_alerts):
    search_query = 'event.value.listValue.values[0].numberValue == 100 && event.value.listValue.values[1].stringValue == "test" && event.value.listValue.values[2].boolValue'
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=3600 / 86400
    )
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    assert len(filtered_alerts) == 1
    assert filtered_alerts[0].source == ["dynamic"]


# tests 10k alerts
@pytest.mark.parametrize(
    "setup_stress_alerts", [{"num_alerts": 10000}], indirect=True
)  # Generate 10,000 alerts
def test_filter_large_dataset(db_session, setup_stress_alerts):
    search_query = '(source == "source_1") && (severity == "critical")'
    start_time = time.time()
    alerts = get_alerts_with_filters(
        tenant_id=SINGLE_TENANT_UUID, time_delta=1
    )  # Assuming `time_delta` is in days
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    end_time = time.time()
    assert len(filtered_alerts) > 0  # Ensure some alerts match the criteria
    print(f"Time taken to filter 10,000 alerts: {end_time - start_time} seconds")


@pytest.mark.parametrize("setup_stress_alerts", [{"num_alerts": 10000}], indirect=True)
def test_complex_logical_operations_large_dataset(db_session, setup_stress_alerts):
    search_query = '((source == "source_3" || source == "source_7") && severity == "warning") || (severity == "critical")'
    start_time = time.time()
    alerts = get_alerts_with_filters(tenant_id=SINGLE_TENANT_UUID, time_delta=1)
    alerts_dto = convert_db_alerts_to_dto_alerts(alerts)
    filtered_alerts = RulesEngine.filter_alerts(alerts_dto, search_query)
    end_time = time.time()

    assert len(filtered_alerts) > 0  # Ensure some alerts match the complex criteria
    print(
        f"Time taken to filter 10,000 alerts with complex criteria: {end_time - start_time} seconds"
    )
