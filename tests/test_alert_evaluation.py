# Tests for Keep Rule Evaluation Engine

from datetime import timedelta

import pytest
from freezegun import freeze_time

from keep.api.models.alert import AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.keep_provider.keep_provider import KeepProvider

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
    context_manager.get_full_context = lambda: context
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
    context_manager.get_full_context = lambda: context
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
    context_manager.get_full_context = lambda: context
    result = keep_provider._notify(**kwargs)
    # Verify alert is resolved
    assert len(result) == 1
    resolved_alert = result[0]
    assert resolved_alert.status == AlertStatus.RESOLVED
    # make sure the lastReceived timestamp is greater than the firing timestamp
    assert resolved_alert.lastReceived > firing_alert.lastReceived


steps_multi_dict = {
    "this": {
        "provider_parameters": {
            "query": "sum(rate(process_cpu_seconds_total)) by (job)",
            "queryType": "query",
        },
        "results": [
            {
                "metric": {"job": "victoriametrics"},
                "value": [1737898557, "0.02330000000000003"],
            },
            {
                "metric": {"job": "vmagent"},
                "value": [1737898557, "0.008633333333333439"],
            },
            {
                "metric": {"job": "vmalert"},
                "value": [1737898557, "0.004199999999999969"],
            },
        ],
    }
}


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": steps_multi_dict,
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
    context_manager.get_full_context = lambda: context
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
            "steps": steps_multi_dict,
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
    context_manager.get_full_context = lambda: context
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
            "steps": steps_multi_dict,
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
    context_manager.get_full_context = lambda: context
    provider = KeepProvider(context_manager, "test", {})

    # Get initial state
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        result = provider._notify(**kwargs)
        assert len(result) == 3
        # Check all alerts are pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics", "vmagent", "vmalert"]

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
            assert alert.labels["job"] in ["victoriametrics", "vmagent", "vmalert"]


@pytest.mark.parametrize(
    "context",
    [
        {
            "steps": steps_multi_dict,
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
    context_manager.get_full_context = lambda: context
    provider = KeepProvider(context_manager, "test", {})

    # Get initial state
    with freeze_time("2024-01-26 10:00:00") as frozen_time:
        result = provider._notify(**kwargs)
        assert len(result) == 3
        # Check all alerts are pending
        for alert in result:
            assert alert.status == AlertStatus.PENDING
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics", "vmagent", "vmalert"]

        # Store initial alerts
        pending_alerts = {a.labels["job"]: a for a in result}

        # Advance time by 1 minute
        frozen_time.tick(delta=timedelta(minutes=1))

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
        # Check alerts transition to firing
        result = provider._notify(**kwargs)
        assert len(result) == 3

        # Verify alerts are now active
        for alert in result:
            assert alert.status == AlertStatus.RESOLVED
            assert alert.lastReceived > pending_alerts[alert.labels["job"]].lastReceived
            assert alert.labels["environment"] == "production"
            assert alert.labels["job"] in ["victoriametrics", "vmagent", "vmalert"]


def test_stateful_alerts_multiple_alerts(db_session, context):
    # test that multiple stateful alerts are created when the condition is met
    pass


def test_stateful_alerts_multiple_alerts_resolved(db_session, context):
    # test that multiple stateful alerts are resolved when the condition is no longer met
    pass
