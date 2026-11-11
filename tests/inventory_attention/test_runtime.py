"""Actual workflow/Slack/ACK adapters, synthetic payload and offline boundaries."""
from dataclasses import asdict
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from test_contract import (db, policy, clock, TENANT, JOB, GRAPH, PRIMARY,
                           fresh_engine, rows, Incident, AuthenticatedEntity)
from keep.api.bl.inventory_attention_runtime import InventoryWorkflow, NativeSlackNotifier
from keep.api.bl.inventory_attention_ack import acknowledge_owned_incident


@pytest.fixture
def config(policy):
    return {"policy": asdict(policy), "fallback_provider_id": "fixture-independent-webhook", "slack_targets": {
        "primary": "U00000001", "backup": "U00000002", "incident_lead": "U00000003"}}


class OfflineOAuthSlack:
    """Only outbound provider boundary is replaced; no HTTP or credentials."""
    authentication_config = SimpleNamespace(access_token="fixture-not-a-token", webhook_url=None)

    def __init__(self):
        self.calls = []

    def _notify(self, **kwargs):
        self.calls.append(kwargs)
        return {"slack_timestamp": kwargs["thread_timestamp"] or "1700000000.000001"}


class OfflineWebhook:
    authentication_config = SimpleNamespace(
        url='https://fixture-independent.example.invalid/attention', method='POST',
        http_basic_authentication_username=None, http_basic_authentication_password=None,
        api_key=None, headers={})

    def _query(self, **kwargs):
        return {'status': True, 'body': {'receipt_id': 'fixture-independent-receipt'}}


def alert(clock, **changes):
    result = dict(inventory_attention_owner="inventory-attention-v1",
                  inventory_observed_at=clock(), inventory_kind="parent_failed",
                  fingerprint="fixture-grafana-fingerprint", job_uuid=JOB,
                  graph_uuid=GRAPH, operation_id="fixture-operation", queue_state="failed",
                  status="firing")
    result.update(changes)
    return result


def test_workflow_restart_payload_to_single_thread_and_escalation(db, config, clock):
    slack = OfflineOAuthSlack()
    notifier = NativeSlackNotifier(slack, config)
    workflow = InventoryWorkflow(db, TENANT, config, notifier, clock)
    first = workflow.run("ingest", alert(clock))
    workflow.run("ingest", alert(clock))
    url = db.url
    db.dispose()
    restarted_engine = fresh_engine(url)
    try:
        resumed = InventoryWorkflow(restarted_engine, TENANT, config, notifier, clock)
        clock.advance(30)
        resumed.run("sweep")
        clock.advance(10)
        resumed.run("sweep")
        resumed.run("sweep")
        recovered = resumed.run("ingest", alert(clock, status="resolved", queue_state="done"))
        assert recovered["status"] == "open"
        assert recovered["incident_id"] == first["incident_id"]
        assert len(rows(restarted_engine, Incident)) == 1
        assert len(slack.calls) == 3
        assert [call["thread_timestamp"] for call in slack.calls] == ["", first["thread_ts"], first["thread_ts"]]
        assert slack.calls[1]["blocks"][0]["text"]["text"] == "<@U00000001>"
        assert slack.calls[2]["blocks"][0]["text"]["text"] == "<@U00000002> <@U00000003>"
        assert all(call["request_timeout"] == 5 for call in slack.calls)
    finally:
        restarted_engine.dispose()


def test_unapproved_source_and_recovery_operation_fail_closed(db, config, clock):
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    with pytest.raises(ValueError):
        workflow.run("ingest", alert(clock, inventory_attention_owner="other"))
    with pytest.raises(ValueError):
        workflow.run("requeue", alert(clock))
    assert not slack.calls
    assert not rows(db, Incident)


def test_slack_evidence_cannot_inject_mentions(db, config, clock):
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    workflow.run("ingest", alert(clock, operation_id="<!channel> fixture"))
    assert slack.calls[0]["blocks"][0]["text"]["type"] == "plain_text"


def test_native_ack_adapter_blocks_technical_ack_and_closure(db, config, clock, monkeypatch):
    monkeypatch.setenv("AUTH_TYPE", "db")
    monkeypatch.setenv("KEEP_IMPERSONATION_ENABLED", "false")
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    state = workflow.run("ingest", alert(clock))
    incident = UUID(state["incident_id"])
    actor = AuthenticatedEntity(tenant_id=TENANT, email=PRIMARY, api_key_name="fixture-api-key")
    with pytest.raises(HTTPException) as technical:
        acknowledge_owned_incident(db, incident, "acknowledged", actor, config)
    assert technical.value.status_code == 403
    human = AuthenticatedEntity(tenant_id=TENANT, email=PRIMARY)
    with pytest.raises(HTTPException) as close:
        acknowledge_owned_incident(db, incident, "resolved", human, config)
    assert close.value.status_code == 409
    assert acknowledge_owned_incident(db, incident, "acknowledged", human, config) is True
    assert workflow.service.snapshot(str(incident))["ack"]["actor"] == PRIMARY


def test_generic_mutation_guards_protect_owned_state_only(db, config, clock):
    from keep.api.bl.inventory_attention_guards import guard_enrichment, guard_incidents
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    state = workflow.run("ingest", alert(clock))
    with pytest.raises(HTTPException) as reserved:
        guard_enrichment(["inventory-policy:fixture-reserved"])
    assert reserved.value.status_code == 409
    with pytest.raises(HTTPException) as owned:
        guard_incidents(db, TENANT, [state["incident_id"]])
    assert owned.value.status_code == 409
    guard_enrichment(["unrelated-fingerprint"])
    guard_incidents(db, TENANT, ["33333333-3333-4333-8333-333333333333"])
    guard_incidents(db, "other-tenant", [state["incident_id"]])


@pytest.mark.parametrize('auth_mode,impersonation', [('noauth', 'false'), ('db', 'true')])
def test_native_ack_rejects_untrusted_identity_configuration(db, config, clock, monkeypatch, auth_mode, impersonation):
    monkeypatch.setenv('AUTH_TYPE', auth_mode)
    monkeypatch.setenv('KEEP_IMPERSONATION_ENABLED', impersonation)
    slack = OfflineOAuthSlack()
    workflow = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    state = workflow.run('ingest', alert(clock))
    human_looking_actor = AuthenticatedEntity(tenant_id=TENANT, email=PRIMARY, api_key_name=None)
    with pytest.raises(HTTPException) as rejected:
        acknowledge_owned_incident(db, UUID(state['incident_id']), 'acknowledged', human_looking_actor, config)
    assert rejected.value.status_code == 403
    assert workflow.service.snapshot(state['incident_id'])['ack'] is None


def test_transport_route_drift_stops_before_new_claim(db, config, clock):
    from copy import deepcopy
    slack = OfflineOAuthSlack()
    original = InventoryWorkflow(db, TENANT, config, NativeSlackNotifier(slack, config), clock)
    original.run('ingest', alert(clock))
    changed = deepcopy(config)
    changed['slack_targets']['primary'] = 'U99999999'
    restarted = InventoryWorkflow(db, TENANT, changed, NativeSlackNotifier(slack, changed), clock)
    clock.advance(30)
    quarantined = restarted.run('sweep')
    assert quarantined[0]['status'] == 'quarantined'
    assert quarantined[0]['coverage_error'] == 'ValueError'
    assert len(slack.calls) == 1


@pytest.mark.parametrize('status', ['firing', 'resolved'])
@pytest.mark.parametrize('error_key', ['Error', 'error'])
def test_grafana_evaluation_error_keeps_uncertainty_despite_original_rule_labels(clock, status, error_key):
    from keep.api.bl.inventory_attention_runtime import signal_from_alert
    raw_error = '[sse.readDataError] [A] got error: input data must be a wide series but got type long (input refid)'
    payload = alert(clock, alertname='Inventory retained failure candidate', status=status,
                    annotations={error_key: raw_error}, business_state='done')
    signal = signal_from_alert(payload)
    assert signal['kind'] == 'coverage_unknown'
    assert signal['evidence']['queue_state'] == 'unknown'
    assert signal['evidence']['business_state'] == 'unknown'
    assert 'datasource_or_evaluation_error' in signal['evidence']['completeness']
    assert raw_error not in str(signal)


def test_empty_grafana_error_does_not_change_verified_failure_classification(clock):
    from keep.api.bl.inventory_attention_runtime import signal_from_alert
    signal = signal_from_alert(alert(clock, annotations={'Error': ''}))
    assert signal['kind'] == 'parent_failed'
    assert signal['evidence']['queue_state'] == 'failed'
