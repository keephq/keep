# Tests for Keep Rule Evaluation Engine

from datetime import timedelta

import pytest
from freezegun import freeze_time

from keep.api.models.alert import AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.keep_provider.keep_provider import KeepProvider
from keep.searchengine.searchengine import SearchEngine

steps_dict = {
    # this is the step that will be used to trigger the alert
    "this": {
        "provider_parameters": {
            "query": "avg(rate(process_cpu_seconds_total))",
            "queryType": "query",
        },
        "results": [
            {
                "metric": {},
                "value": [],
            }
        ],
    },
}


# generate a dictionary with multiple results
# that "mocks" results of victoriametrics
def genereate_multi_dict(job_prefix: str):
    return {
        "this": {
            "provider_parameters": {
                "query": "sum(rate(process_cpu_seconds_total)) by (job)",
                "queryType": "query",
            },
            "results": [
                {
                    "metric": {"job": "victoriametrics" + job_prefix},
                    "value": [1737898557, "0.02330000000000003"],
                },
                {
                    "metric": {"job": "vmagent" + job_prefix},
                    "value": [1737898557, "0.008633333333333439"],
                },
                {
                    "metric": {"job": "vmalert" + job_prefix},
                    "value": [1737898557, "0.004199999999999969"],
                },
            ],
        }
    }


@pytest.mark.parametrize(
    ["context", "severity", "if_condition", "value"],
    [
        (
            # should not trigger
            {
                "steps": steps_dict,
            },
            None,
            "{{ value.1 }} > 0.01",
            [1737891487, "0.001"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "info",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.012699999999999975"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "warning",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.81"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "critical",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.91"],
        ),
    ],
)
def test_stateless_alerts_firing(db_session, context, severity, if_condition, value):
    """Test alerts without 'for' duration - should go straight to FIRING"""
    kwargs = {
        "alert": {
            "description": "[Single] CPU usage is high on the VM (created from VM metric)",
            "labels": {
                "app": "myapp",
                "environment": "production",
                "owner": "alice",
                "service": "api",
                "team": "devops",
            },
            "name": "High CPU Usage",
            "severity": '{{ value.1 }} > 0.9 ? "critical" : {{ value.1 }} > 0.7 ? "warning" : "info"',
        },
        "if": if_condition,
    }
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context["steps"]["this"]["results"][0]["value"] = value
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    keep_provider = KeepProvider(context_manager, "test", {})
    result = keep_provider._notify(**kwargs)

    # alert should not trigger if severity is None
    if not severity:
        return

    assert len(result) == 1

    alert = result[0]
    assert alert.status == AlertStatus.FIRING
    assert alert.name == "High CPU Usage"
    assert (
        alert.description
        == "[Single] CPU usage is high on the VM (created from VM metric)"
    )
    assert alert.severity == severity
    assert alert.labels == {
        "app": "myapp",
        "environment": "production",
        "owner": "alice",
        "service": "api",
        "team": "devops",
    }


@pytest.mark.parametrize(
    ["context", "severity", "if_condition", "firing_value", "resolved_value"],
    [
        (
            # should not trigger
            {
                "steps": steps_dict,
            },
            None,
            "{{ value.1 }} > 0.01",
            [1737891487, "0.001"],
            [1737891487, "0.001"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "info",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.012699999999999975"],
            [1737891487, "0.001"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "warning",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.81"],
            [1737891487, "0.001"],
        ),
        (
            {
                "steps": steps_dict,
            },
            "critical",
            "{{ value.1 }} > 0.01",
            [1737891487, "0.91"],
            [1737891487, "0.001"],
        ),
    ],
)
def test_stateless_alerts_resolved(
    db_session, context, severity, if_condition, firing_value, resolved_value
):
    """Test that alerts transition from FIRING to RESOLVED when condition no longer met"""
    kwargs = {
        "alert": {
            "description": "[Single] CPU usage is high on the VM (created from VM metric)",
            "labels": {
                "app": "myapp",
                "environment": "production",
                "owner": "alice",
                "service": "api",
                "team": "devops",
            },
            "name": "High CPU Usage",
            "severity": '{{ value.1 }} > 0.9 ? "critical" : {{ value.1 }} > 0.7 ? "warning" : "info"',
        },
        "if": if_condition,
    }

    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context["steps"]["this"]["results"][0]["value"] = firing_value
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    keep_provider = KeepProvider(context_manager, "test", {})
    # First trigger the alert with firing value
    result = keep_provider._notify(**kwargs)

    # Verify initial firing state
    if not severity:
        assert not result
        return

    assert len(result) == 1
    firing_alert = result[0]
    assert firing_alert.status == AlertStatus.FIRING
    assert firing_alert.severity == severity

    # Now update with resolved value
    context["steps"]["this"]["results"][0]["value"] = resolved_value
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    result = keep_provider._notify(**kwargs)
    # Verify alert is resolved
    assert len(result) == 1
    resolved_alert = result[0]
    assert resolved_alert.status == AlertStatus.RESOLVED
    # make sure the lastReceived timestamp is greater than the firing timestamp
    assert resolved_alert.lastReceived > firing_alert.lastReceived


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict(""),
        }
    ],
)
def test_statless_alerts_multiple_alerts(db_session, context):
    """Test that multiple alerts are created when the condition is met"""
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
    }
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider = KeepProvider(context_manager, "test", {})
    result = provider._notify(**kwargs)
    assert len(result) == 3

    # Check victoriametrics alert
    vm_alert = next(a for a in result if a.labels["job"] == "victoriametrics")
    assert vm_alert.status == AlertStatus.FIRING
    assert vm_alert.name == "High CPU Usage - victoriametrics"
    assert vm_alert.description == "CPU usage is high on victoriametrics"
    assert vm_alert.severity == "critical"

    # Check vmagent alert
    vmagent_alert = next(a for a in result if a.labels["job"] == "vmagent")
    assert vmagent_alert.status == AlertStatus.FIRING
    assert vmagent_alert.name == "High CPU Usage - vmagent"
    assert vmagent_alert.description == "CPU usage is high on vmagent"
    assert vmagent_alert.severity == "info"

    # Check vmalert alert
    vmalert_alert = next(a for a in result if a.labels["job"] == "vmalert")
    assert vmalert_alert.status == AlertStatus.FIRING
    assert vmalert_alert.name == "High CPU Usage - vmalert"
    assert vmalert_alert.description == "CPU usage is high on vmalert"
    assert vmalert_alert.severity == "info"


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict(""),
        }
    ],
)
def test_stateless_alerts_multiple_alerts_resolved(db_session, context):
    """Test that multiple alerts are resolved when the condition is no longer met"""
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
    }

    # First create firing alerts
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider = KeepProvider(context_manager, "test", {})
    result = provider._notify(**kwargs)
    assert len(result) == 3
    firing_alerts = {a.labels["job"]: a for a in result}

    # Update values to be below threshold
    context["steps"]["this"]["results"] = [
        {
            "metric": {"job": "victoriametrics"},
            "value": [1737898558, "0.0001"],
        },
        {
            "metric": {"job": "vmagent"},
            "value": [1737898558, "0.0001"],
        },
        {
            "metric": {"job": "vmalert"},
            "value": [1737898558, "0.0001"],
        },
    ]

    # Check resolved alerts
    result = provider._notify(**kwargs)
    assert len(result) == 3

    for alert in result:
        assert alert.status == AlertStatus.RESOLVED
        assert alert.lastReceived > firing_alerts[alert.labels["job"]].lastReceived
        assert alert.labels["environment"] == "production"
        assert alert.labels["job"] in ["victoriametrics", "vmagent", "vmalert"]


#### Stateful Alerts ####


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict("2"),
        }
    ],
)
def test_stateful_alerts_firing(db_session, context):
    """Test that multiple alerts transition from pending to firing after time condition is met"""
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }

    # First create pending alerts
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider = KeepProvider(context_manager, "test", {})

    # Get initial state
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        result = provider._notify(**kwargs)
        assert len(result) == 3
        # Check all alerts are pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics2", "vmagent2", "vmalert2"]

        # Store initial alerts
        pending_alerts = {a.labels["job"]: a for a in result}

        # Advance time by 1 minute
        frozen_time.tick(delta=timedelta(minutes=1))

        # Check alerts transition to firing
        result = provider._notify(**kwargs)
        assert len(result) == 3

        # Verify alerts are now active
        for alert in result:
            assert alert.status == AlertStatus.FIRING
            assert alert.lastReceived > pending_alerts[alert.labels["job"]].lastReceived
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics2", "vmagent2", "vmalert2"]


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict("3"),
        }
    ],
)
def test_stateful_alerts_resolved(db_session, context):
    """Test that multiple alerts transition from firing to resolved after time condition is met"""
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }

    # First create pending alerts
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context_manager.context = context
    context_manager.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider = KeepProvider(context_manager, "test", {})

    # Get initial state
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        result = provider._notify(**kwargs)
        assert len(result) == 3
        # Check all alerts are pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics3", "vmagent3", "vmalert3"]

        # Store initial alerts
        pending_alerts = {a.labels["job"]: a for a in result}

        # Advance time by 1 minute
        frozen_time.tick(delta=timedelta(minutes=1))

        # Update values to be below threshold
        context["steps"]["this"]["results"] = [
            {
                "metric": {"job": "victoriametrics3"},
                "value": [1737898558, "0.0001"],
            },
            {
                "metric": {"job": "vmagent3"},
                "value": [1737898558, "0.0001"],
            },
            {
                "metric": {"job": "vmalert3"},
                "value": [1737898558, "0.0001"],
            },
        ]
        # Check alerts transition to firing
        result = provider._notify(**kwargs)
        assert len(result) == 3

        # Verify alerts are now active
        for alert in result:
            assert alert.status == AlertStatus.RESOLVED
            assert alert.lastReceived > pending_alerts[alert.labels["job"]].lastReceived
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics3", "vmagent3", "vmalert3"]


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict("4"),
        }
    ],
)
def test_stateful_alerts_multiple_alerts(db_session, context):
    # test that multiple stateful alerts are created when the condition is met
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }
    # create few alerts
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
        context_manager.context = context
        context_manager.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context
        )
        provider = KeepProvider(context_manager, "test", {})
        result = provider._notify(**kwargs)
        assert len(result) == 3

        # all of them should be pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING

        # now create few more alerts
        more_alerts = genereate_multi_dict("6")
        context["steps"] = more_alerts
        context_manager.get_full_context = (
            lambda exclude_providers, exclude_env: context
        )
        result = provider._notify(**kwargs)
        assert len(result) == 6

        # 3 of them should be RESOLVED (since they are not exists in the results) and 3 should be FIRING
        for alert in result:
            if alert.labels["job"] in ["victoriametrics6", "vmagent6", "vmalert6"]:
                assert alert.status == AlertStatus.PENDING
            else:
                assert alert.status == AlertStatus.RESOLVED

        # now we should have 6 alerts on pending
        search_engine = SearchEngine(tenant_id=context_manager.tenant_id)
        alerts = search_engine.search_alerts_by_cel(cel_query="1 == 1")
        assert len(alerts) == 6

        # now let's advance time by 2 minute
        frozen_time.tick(delta=timedelta(minutes=2))

        result = provider._notify(**kwargs)
        # 3 should be FIRING and 3 should be RESOLVED
        assert len(result) == 6
        for alert in result:
            if alert.labels["job"] in ["victoriametrics6", "vmagent6", "vmalert6"]:
                assert alert.status == AlertStatus.FIRING
            else:
                assert alert.status == AlertStatus.RESOLVED


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict("5"),
        }
    ],
)
def test_stateful_alerts_multiple_alerts_2(db_session, context):
    # test that multiple stateful alerts are created when the condition is met
    kwargs = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }
    # create few alerts
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
        context_manager.context = context
        context_manager.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context
        )
        provider = KeepProvider(context_manager, "test", {})
        result = provider._notify(**kwargs)
        assert len(result) == 3

        # all of them should be pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 2 minute
        frozen_time.tick(delta=timedelta(seconds=30))

        result = provider._notify(**kwargs)
        # should be still pending
        assert len(result) == 3
        for alert in result:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 1 minute
        frozen_time.tick(delta=timedelta(minutes=1))

        result = provider._notify(**kwargs)
        # should be FIRING
        assert len(result) == 3
        for alert in result:
            assert alert.status == AlertStatus.FIRING


def test_state_alerts_multiple_firing_transitions(db_session):
    """Test scenario where some alerts go FIRING while others remain PENDING
    - Create 6 alerts all PENDING
    - Set 3 alerts to pass 'for' duration threshold
    - Verify 3 alerts go FIRING, 3 stays PENDING
    """
    # test that multiple stateful alerts are created when the condition is met
    context1 = {
        "steps": genereate_multi_dict("ctx1"),
    }
    context2 = {
        "steps": genereate_multi_dict("ctx2"),
    }
    kwargs1 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }
    kwargs2 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "5m",
    }
    # create few alerts
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        context_manager1 = ContextManager(
            tenant_id="test", workflow_id="test-workflow-1"
        )
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        provider1 = KeepProvider(context_manager1, "test", {})

        context_manager2 = ContextManager(
            tenant_id="test", workflow_id="test-workflow-2"
        )
        context_manager2.context = context2
        context_manager2.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context2
        )
        provider2 = KeepProvider(context_manager2, "test", {})

        # create 3 alerts
        result = provider1._notify(**kwargs1)
        assert len(result) == 3

        # all of them should be pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING

        # create another 3 alerts
        result = provider2._notify(**kwargs2)
        assert len(result) == 3
        for alert in result:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 1 minute
        frozen_time.tick(delta=timedelta(minutes=1))

        result1 = provider1._notify(**kwargs1)
        result2 = provider2._notify(**kwargs2)
        # should be FIRING
        assert len(result1) == 3
        for alert in result1:
            assert alert.status == AlertStatus.FIRING

        # should be still pending (cuz only 1m passed and not 5m)
        assert len(result2) == 3
        for alert in result2:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 5 minutes
        frozen_time.tick(delta=timedelta(minutes=5))

        result1 = provider1._notify(**kwargs1)
        result2 = provider2._notify(**kwargs2)
        # should be FIRING
        assert len(result1) == 3
        for alert in result1:
            assert alert.status == AlertStatus.FIRING

        assert len(result2) == 3
        for alert in result2:
            assert alert.status == AlertStatus.FIRING


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": genereate_multi_dict("3"),
        }
    ],
)
def test_make_sure_two_different_workflows_have_different_fingerprints(
    db_session, context
):
    """Test that two different workflows have different fingerprints (this is because different workflows have different workflowId which is used in the fingerprint calculation)"""
    kwargs1 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
    }

    kwargs2 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
    }

    context_manager1 = ContextManager(tenant_id="test", workflow_id="test-workflow-1")
    context_manager1.context = context
    context_manager1.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider1 = KeepProvider(context_manager1, "test", {})

    context_manager2 = ContextManager(tenant_id="test", workflow_id="test-workflow-2")
    context_manager2.context = context
    context_manager2.get_full_context = (
        lambda exclude_providers=False, exclude_env=False: context
    )
    provider2 = KeepProvider(context_manager2, "test", {})

    result1 = provider1._notify(**kwargs1)
    result2 = provider2._notify(**kwargs2)

    assert len(result1) == 3
    assert len(result2) == 3

    assert set([alert.fingerprint for alert in result1]) != set(
        [alert.fingerprint for alert in result2]
    )


def test_state_alerts_staggered_resolution(db_session):
    """Test alerts resolving at different times
    - Create 3 FIRING alerts
    - Remove 1 alert from results
    - Verify it goes RESOLVED while others stay FIRING
    - Remove another alert
    - Verify correct state transitions
    """
    context1 = {
        "steps": genereate_multi_dict("staggered"),
    }

    kwargs1 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }
    # create few alerts
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        context_manager1 = ContextManager(
            tenant_id="test", workflow_id="test-workflow-1"
        )
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        provider1 = KeepProvider(context_manager1, "test", {})

        result1 = provider1._notify(**kwargs1)
        assert len(result1) == 3
        for alert in result1:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 1 minute and remove 1 alert
        frozen_time.tick(delta=timedelta(minutes=1))

        # remove 1 alert
        context1["steps"]["this"]["results"] = [
            alert
            for alert in context1["steps"]["this"]["results"]
            if alert["metric"]["job"] != "vmagentstaggered"
        ]
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        result1 = provider1._notify(**kwargs1)
        assert len(result1) == 3
        for alert in result1:
            if alert.labels["job"] == "vmagentstaggered":
                assert alert.status == AlertStatus.RESOLVED
            else:
                assert alert.status == AlertStatus.FIRING


def test_state_alerts_flapping(db_session):
    """Test alert flapping behavior
    - Create alert in PENDING
    - Remove it before 'for' duration -> should be dropped
    - Reintroduce alert -> should start fresh PENDING
    - Test this pattern multiple times
    """
    context1 = {
        "steps": genereate_multi_dict("flapping"),
    }

    kwargs1 = {
        "alert": {
            "description": "CPU usage is high on {{ metric.job }}",
            "labels": {
                "job": "{{ metric.job }}",
                "environment": "production",
            },
            "name": "High CPU Usage - {{ metric.job }}",
            "severity": '{{ value.1 }} > 0.02 ? "critical" : {{ value.1 }} > 0.01 ? "warning" : "info"',
        },
        "if": "{{ value.1 }} > 0.001",
        "for": "1m",
    }
    # create few alerts
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        context_manager1 = ContextManager(
            tenant_id="test", workflow_id="test-workflow-1"
        )
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        provider1 = KeepProvider(context_manager1, "test", {})

        result1 = provider1._notify(**kwargs1)
        assert len(result1) == 3
        for alert in result1:
            assert alert.status == AlertStatus.PENDING

        # now let's advance time by 30 seconds (still pending)
        frozen_time.tick(delta=timedelta(seconds=30))
        # and remove 1 alert
        removed_alert = [
            alert
            for alert in context1["steps"]["this"]["results"]
            if alert["metric"]["job"] == "vmagentflapping"
        ][0]
        context1["steps"]["this"]["results"] = [
            alert
            for alert in context1["steps"]["this"]["results"]
            if alert["metric"]["job"] != "vmagentflapping"
        ]
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        result1 = provider1._notify(**kwargs1)
        # so now we have 2 alerts pending and 1 alert resolved
        assert len(result1) == 3
        for alert in result1:
            if alert.labels["job"] == "vmagentflapping":
                assert alert.status == AlertStatus.RESOLVED
            else:
                assert alert.status == AlertStatus.PENDING

        # now let's advance time by 1 minute and return the alert
        frozen_time.tick(delta=timedelta(minutes=1))
        context1["steps"]["this"]["results"].append(removed_alert)
        context_manager1.context = context1
        context_manager1.get_full_context = (
            lambda exclude_providers=False, exclude_env=False: context1
        )
        # it should be 2 firing and 1 pending
        result1 = provider1._notify(**kwargs1)
        assert len(result1) == 3
        for alert in result1:
            if alert.labels["job"] == "vmagentflapping":
                assert alert.status == AlertStatus.PENDING
            else:
                assert alert.status == AlertStatus.FIRING
