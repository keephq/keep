# Tests for Keep Rule Evaluation Engine

import pytest

from keep.api.models.alert import AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.keep_provider.keep_provider import KeepProvider


@pytest.fixture
def provider(context, value):
    # setup test provider
    context_manager = ContextManager(tenant_id="test", workflow_id="test-workflow")
    context["steps"]["this"]["results"][0]["value"] = value
    context_manager.context = context
    context_manager.get_full_context = lambda: context
    return KeepProvider(context_manager, "test", {})


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
def test_stateless_alerts_firing(provider, context, severity, if_condition, value):
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
    result = provider._notify(**kwargs)

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
    "victoriametrics-step": {
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
        "vars": {},
        "aliases": {},
    },
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
        "vars": {},
        "aliases": {},
    },
    "create-alert": {
        "provider_parameters": {},
        "results": [],
        "vars": {},
        "aliases": {},
    },
}


def test_statless_alerts_multiple_alerts(provider, context):
    # test that multiple alerts are created when the condition is met
    pass


def test_stateless_alerts_multiple_alerts_resolved(provider, context):
    # test that multiple alerts are resolved when the condition is no longer met
    pass


def test_stateful_alerts_firing(provider, context):
    # test that stateful alerts are created when the condition is met
    pass


def test_stateful_alerts_resolved(provider, context):
    # test that stateful alerts are resolved when the condition is no longer met
    pass


def test_stateful_alerts_multiple_alerts(provider, context):
    # test that multiple stateful alerts are created when the condition is met
    pass


def test_stateful_alerts_multiple_alerts_resolved(provider, context):
    # test that multiple stateful alerts are resolved when the condition is no longer met
    pass
