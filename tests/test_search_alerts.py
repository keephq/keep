import os
import time

import pytest

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import AlertActionType
from keep.api.models.db.mapping import MappingRule
from keep.api.models.db.preset import PresetSearchQuery as SearchQuery
from keep.searchengine.searchengine import SearchEngine
from tests.test_deduplications import wait_for_alerts  # noqa

# Shahar: If you are struggling - you can play with https://playcel.undistro.io/ to see how the CEL expressions work


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(source in (:source_1))",
            "params": {
                "source_1": "grafana",
            },
        },
        cel_query="(source == 'grafana')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1

    # compare the results
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(source = :source_1 OR source = :source_2)",
            "params": {
                "source_1": "sentry",
                "source_2": "grafana",
            },
        },
        cel_query="(source == 'sentry' || source == 'grafana')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 2
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 2

    # compare the results
    sorted_elastic_alerts = sorted(
        elastic_filtered_alerts, key=lambda x: x.lastReceived
    )
    sorted_db_alerts = sorted(db_filtered_alerts, key=lambda x: x.lastReceived)
    assert sorted_elastic_alerts == sorted_db_alerts


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
    search_query = SearchQuery(
        sql_query={
            "sql": "NOT ((source = :source_1 or source = :source_2))",
            "params": {"source_1": "sentry", "source_2": "grafana"},
        },
        cel_query="!(source == 'sentry' || source == 'grafana')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 0
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 0


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
    # mark alerts as dismissed
    enrichment_bl = EnrichmentsBl(SINGLE_TENANT_UUID)
    enrichment_bl.enrich_alert(
        fingerprint="test-1",
        enrichments={"dismissed": True},
        action_callee="test",
        action_description="test",
        action_type=AlertActionType.GENERIC_ENRICH,
    )
    search_query = SearchQuery(
        sql_query={
            "sql": "((source = :source_1 or source = :source_2) and dismissed != :dismissed_1)",
            "params": {
                "source_1": "sentry",
                "source_2": "grafana",
                "dismissed_1": "true",
            },
        },
        cel_query="((source == 'sentry' || source == 'grafana') && !dismissed)",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(labels.some_label = :labels.some_label_1)",
            "params": {"labels.some_label_1": "some_value"},
        },
        cel_query='(labels.some_label == "some_value")',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 2
    assert sorted(
        list(set([alert.fingerprint for alert in elastic_filtered_alerts]))
    ) == sorted(["test-2", "test-1"])
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 2
    assert sorted(
        list(set([alert.fingerprint for alert in db_filtered_alerts]))
    ) == sorted(["test-2", "test-1"])
    # compare sort by fingerprint
    assert sorted(elastic_filtered_alerts, key=lambda x: x.fingerprint) == sorted(
        db_filtered_alerts, key=lambda x: x.fingerprint
    )


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(labels.some_label like :labels.some_label_1)",
            "params": {"labels.some_label_1": "%bla%"},
        },
        cel_query='(labels.some_label.contains("bla"))',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 2
    assert sorted(
        list(set([alert.fingerprint for alert in elastic_filtered_alerts]))
    ) == sorted(["test-2", "test-1"])

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 2
    assert sorted(
        list(set([alert.fingerprint for alert in db_filtered_alerts]))
    ) == sorted(["test-2", "test-1"])
    # compare sort by fingerprint
    assert sorted(elastic_filtered_alerts, key=lambda x: x.fingerprint) == sorted(
        db_filtered_alerts, key=lambda x: x.fingerprint
    )


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(count > :count_1)",
            "params": {"count_1": 6},
        },
        cel_query="(count > 6)",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].source == ["application"]
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].source == ["application"]
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]
    # check the count
    assert elastic_filtered_alerts[0].count == 10


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(severity != :severity_1)",
            "params": {"severity_1": "critical"},
        },
        cel_query="(severity != 'critical')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].severity == "warning"

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].severity == "warning"
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {
                    "source": ["sentry", "datadog"],
                    "severity": "warning",
                    "some_list": ["a", "b"],
                },
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_list(db_session, setup_alerts):
    search_query = SearchQuery(
        sql_query={
            "sql": "(severity != :severity_1)",
            "params": {"severity_1": "critical"},
        },
        cel_query="(severity != 'critical')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].severity == "warning"
    assert elastic_filtered_alerts[0].some_list == ["a", "b"]

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].severity == "warning"
    assert db_filtered_alerts[0].some_list == ["a", "b"]
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


@pytest.mark.parametrize(
    "setup_alerts",
    [
        {
            "alert_details": [
                {
                    "source": ["sentry", "datadog"],
                    "severity": "warning",
                    "some_dict": {
                        "a": 1,
                        "b": 2,
                        "c": [1, 2, 3],
                        "d": {"a": 1, "b": 2, "c": [1, 2, 3]},
                    },
                },
                {"source": ["grafana"], "severity": "critical"},
            ]
        }
    ],
    indirect=True,
)
def test_dict(db_session, setup_alerts):
    search_query = SearchQuery(
        sql_query={
            "sql": "(severity != :severity_1)",
            "params": {"severity_1": "critical"},
        },
        cel_query="(severity != 'critical')",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].severity == "warning"
    assert elastic_filtered_alerts[0].some_dict == {
        "a": 1,
        "b": 2,
        "c": [1, 2, 3],
        "d": {"a": 1, "b": 2, "c": [1, 2, 3]},
    }

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].severity == "warning"
    assert db_filtered_alerts[0].some_dict == {
        "a": 1,
        "b": 2,
        "c": [1, 2, 3],
        "d": {"a": 1, "b": 2, "c": [1, 2, 3]},
    }
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "NOT (active = :active_1)",
            "params": {"active_1": True},
        },
        cel_query="!(active)",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].active == False
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].active == False
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(user in (:user_1, :user_2))",
            "params": {"user_1": "admin", "user_2": "backend"},
        },
        cel_query='(user in ["admin", "backend"])',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].user == "admin"
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].user == "admin"
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(path like :path_1)",
            "params": {"path_1": "/api%"},
        },
        cel_query='(path.startsWith("/api"))',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].path == "/api/data"
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].path == "/api/data"
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(assigned is null)",
            "params": {},
        },
        cel_query="(assigned == null)",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].assignee == None
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].assignee == None

    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "((metrics.requests > :metrics.requests_1) AND (metrics.errors.timeout > :metrics.errors.timeout_1 OR metrics.errors.server < :metrics.errors.server_1))",
            "params": {
                "metrics.requests_1": 100,
                "metrics.errors.timeout_1": 15,
                "metrics.errors.server_1": 1,
            },
        },
        cel_query="((metrics.requests > 100) && (metrics.errors.timeout > 15 || metrics.errors.server < 1))",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].source == ["database"]
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].source == ["database"]
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
    search_query = SearchQuery(
        sql_query={
            "sql": "(endpoint = :endpoint_1)",
            "params": {"endpoint_1": "/auth/login?redirect=/home"},
        },
        cel_query='(endpoint == "/auth/login?redirect=/home")',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].endpoint == "/auth/login?redirect=/home"
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].endpoint == "/auth/login?redirect=/home"
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


# tests 10k alerts
@pytest.mark.parametrize(
    "setup_stress_alerts", [{"num_alerts": 1000}], indirect=True
)  # Generate 10,000 alerts
def test_filter_large_dataset(db_session, setup_stress_alerts):
    search_query = SearchQuery(
        sql_query={
            "sql": "(source = :source_1) AND (severity = :severity_1)",
            "params": {"source_1": "source_1", "severity_1": "critical"},
        },
        cel_query='(source == "source_1") && (severity == "critical")',
        limit=1000,
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_start_time = time.time()
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    elastic_end_time = time.time()
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_start_time = time.time()
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    db_end_time = time.time()
    # compare
    assert len(elastic_filtered_alerts) == len(db_filtered_alerts)
    print(
        "time taken for 1k alerts with elastic: ",
        elastic_end_time - elastic_start_time,
    )
    print("time taken for 1k alerts with db: ", db_end_time - db_start_time)


@pytest.mark.parametrize("setup_stress_alerts", [{"num_alerts": 10000}], indirect=True)
def test_complex_logical_operations_large_dataset(db_session, setup_stress_alerts):
    search_query = SearchQuery(
        sql_query={
            "sql": "((source = :source_1 OR source = :source_2) AND severity = :severity_1) OR (severity = :severity_2)",
            "params": {
                "source_1": "source_1",
                "source_2": "source_2",
                "severity_1": "critical",
                "severity_2": "warning",
            },
        },
        cel_query='((source == "source_1" || source == "source_2") && severity == "critical") || (severity == "warning")',
        limit=10000,
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_start_time = time.time()
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    elastic_end_time = time.time()
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_start_time = time.time()
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    db_end_time = time.time()
    # compare
    assert len(elastic_filtered_alerts) == len(db_filtered_alerts)
    print(
        "time taken for 10k alerts with elastic: ",
        elastic_end_time - elastic_start_time,
    )
    print("time taken for 10k alerts with db: ", db_end_time - db_start_time)


@pytest.mark.parametrize("setup_stress_alerts", [{"num_alerts": 10000}], indirect=True)
def test_last_1000(db_session, setup_stress_alerts):
    search_query = SearchQuery(
        sql_query={"sql": "(deleted=false AND dismissed=false)", "params": {}},
        cel_query="(!deleted && !dismissed)",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_start_time = time.time()
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    elastic_end_time = time.time()
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_start_time = time.time()
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    db_end_time = time.time()
    # check that these are the last 1000 alerts
    assert len(elastic_filtered_alerts) == 1000
    # check that these ordered by lastReceived
    assert (
        sorted(elastic_filtered_alerts, key=lambda x: x.lastReceived, reverse=True)
        == elastic_filtered_alerts
    )
    # compare
    assert len(elastic_filtered_alerts) == len(db_filtered_alerts)

    print(
        "time taken for 10k alerts with elastic: ",
        elastic_end_time - elastic_start_time,
    )
    print("time taken for 10k alerts with db: ", db_end_time - db_start_time)


# Assuming setup_alerts is a fixture that sets up the database with specified alert details
alert_details = {
    "alert_details": [
        {"source": ["test"], "severity": "critical"},
        {"source": ["test"], "severity": "high"},
        {"source": ["test"], "severity": "warning"},
        {"source": ["test"], "severity": "info"},
        {"source": ["test"], "severity": "low"},
    ]
}


@pytest.mark.parametrize(
    "setup_alerts, search_query, expected_severity_counts",
    [
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity == "critical"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity == "high"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity == "warning"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity == "info"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity == "low"',
            ),
            1,
        ),
        # Inequality tests
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity != :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity != "critical"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity != :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity != "high"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity != :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity != "warning"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity != :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity != "info"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity != :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity != "low"',
            ),
            4,
        ),
        # Greater than tests
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity > :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity > "critical"',
            ),
            0,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity > :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity > "high"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity > :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity > "warning"',
            ),
            2,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity > :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity > "info"',
            ),
            3,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity > :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity > "low"',
            ),
            4,
        ),
        # Less than tests
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity < :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity < "critical"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity < :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity < "high"',
            ),
            3,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity < :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity < "warning"',
            ),
            2,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity < :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity < "info"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity < :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity < "low"',
            ),
            0,
        ),
        # Greater than or equal tests
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity >= :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity >= "critical"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity >= :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity >= "high"',
            ),
            2,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity >= :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity >= "warning"',
            ),
            3,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity >= :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity >= "info"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity >= :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity >= "low"',
            ),
            5,
        ),
        # Less than or equal tests
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity <= :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity <= "critical"',
            ),
            5,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity <= :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity <= "high"',
            ),
            4,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity <= :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query='severity <= "warning"',
            ),
            3,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity <= :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity <= "info"',
            ),
            2,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity <= :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity <= "low"',
            ),
            1,
        ),
        # spaces
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query='severity=="critical"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query='severity == "high"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query=' severity== "warning"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "info"},
                },
                cel_query='severity== "info"',
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "low"},
                },
                cel_query='severity =="low"',
            ),
            1,
        ),
        # single quotes
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "critical"},
                },
                cel_query="severity == 'critical'",
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "high"},
                },
                cel_query="severity == 'high' ",
            ),
            1,
        ),
        (
            alert_details,
            SearchQuery(
                sql_query={
                    "sql": "(severity = :severity_1)",
                    "params": {"severity_1": "warning"},
                },
                cel_query="severity =='warning'",
            ),
            1,
        ),
    ],
    indirect=["setup_alerts"],
)
def test_severity_comparisons(
    db_session, setup_alerts, search_query, expected_severity_counts
):
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(elastic_filtered_alerts) == expected_severity_counts

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query
    )
    assert len(db_filtered_alerts) == expected_severity_counts

    # compare
    assert set([alert.id for alert in elastic_filtered_alerts]) == set(
        [alert.id for alert in db_filtered_alerts]
    )


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_alerts_enrichment_in_search(db_session, client, test_app, elastic_client):

    rule = MappingRule(
        id=1,
        tenant_id=SINGLE_TENANT_UUID,
        priority=1,
        matchers=["name", "severity"],
        rows=[
            {"severity": "low", "status": "dismissed"},
            {"severity": "high", "service": "high_severity_service"},
        ],
        name="new_rule",
        disabled=False,
    )
    db_session.add(rule)
    db_session.commit()

    alert_high_dto = AlertDto(
        id="test_high_id",
        name="Test High Alert",
        status="firing",
        severity="high",
        lastReceived="2021-01-01T00:00:00Z",
        source=["test_source"],
        labels={},
    )
    alert_low_dto = AlertDto(
        id="test_low_id",
        name="Test Low Alert",
        status="firing",
        severity="low",
        fingerprint="test-alert",
        lastReceived="2021-01-01T00:00:00Z",
        source=["test_source_low"],
        labels={},
    )

    search_query_high = SearchQuery(
        sql_query={
            "sql": "(source in (:source_1))",
            "params": {
                "source_1": "test_source",
            },
        },
        cel_query="(source == 'test_source')",
    )

    search_query_low = SearchQuery(
        sql_query={
            "sql": "(source in (:source_1))",
            "params": {
                "source_1": "test_source_low",
            },
        },
        cel_query="(source == 'test_source_low')",
    )

    # Create alert without enrichment rules
    client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=alert_low_dto.dict(),
    )
    # And another with them
    client.post(
        "/alerts/event",
        headers={"x-api-key": "some-key"},
        json=alert_high_dto.dict(),
    )

    wait_for_alerts(client, 2)

    # And add manual enrichment
    client.post(
        "/alerts/enrich",
        headers={"x-api-key": "some-key"},
        json={
            "fingerprint": alert_high_dto.fingerprint,
            "enrichments": {
                "note": "test note",
            },
        },
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"

    # Test alert without enrichments
    elastic_filtered_low_alerts = SearchEngine(
        tenant_id=SINGLE_TENANT_UUID
    ).search_alerts(search_query_low)
    assert len(elastic_filtered_low_alerts) == 1

    elastic_filtered_low_alert = elastic_filtered_low_alerts[0].dict()

    assert "enriched_fields" in elastic_filtered_low_alert
    assert elastic_filtered_low_alert["enriched_fields"] == [
        "status"
    ]  # status was enriched by the mapping rule

    # Now let's get alert with some enrichments
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query_high
    )
    assert len(elastic_filtered_alerts) == 1

    elastic_filtered_alert = elastic_filtered_alerts[0].dict()

    assert "note" in elastic_filtered_alert
    assert elastic_filtered_alert["note"] == "test note"
    assert "enriched_fields" in elastic_filtered_alert
    assert sorted(elastic_filtered_alert["enriched_fields"]) == ["note", "service"]

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(
        search_query_high
    )
    assert len(db_filtered_alerts) == 1

    db_filtered_alert = db_filtered_alerts[0].dict()

    assert "note" in db_filtered_alert
    assert db_filtered_alert["note"] == "test note"
    assert "enriched_fields" in db_filtered_alert
    assert sorted(db_filtered_alert["enriched_fields"]) == ["note", "service"]


"""
COMMENTED OUT UNTIL WE FIGURE ' something in list'

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
    search_query = SearchQuery(
        sql_query={
            "sql": "((responseTimes[0] < :responseTimes_1 OR responseTimes[1] > :responseTimes_2) AND status = :status_1)",
            "params": {"responseTimes_1": 200, "responseTimes_2": 200, "status_1": "resolved"},
        },
        cel_query='((responseTimes[0] < 200 || responseTimes[1] > 200) && status == "resolved")',
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(search_query)
    assert len(elastic_filtered_alerts) == 1

    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(search_query)
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].source == ["frontend"]
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]

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
    search_query = SearchQuery(
        sql_query={
            "sql": "(queue = :queue_1)",
            "params": {"queue_1": []},
        },
        cel_query="(queue == [])",
    )
    # first, use elastic
    os.environ["ELASTIC_ENABLED"] = "true"
    elastic_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(search_query)
    assert len(elastic_filtered_alerts) == 1
    assert elastic_filtered_alerts[0].source == ["job"]
    # then, use db
    os.environ["ELASTIC_ENABLED"] = "false"
    db_filtered_alerts = SearchEngine(tenant_id=SINGLE_TENANT_UUID).search_alerts(search_query)
    assert len(db_filtered_alerts) == 1
    assert db_filtered_alerts[0].source == ["job"]
    # compare
    assert elastic_filtered_alerts[0] == db_filtered_alerts[0]


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
"""
