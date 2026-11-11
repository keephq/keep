"""Human resolution is an audited attestation, never inferred from queue state."""
from uuid import UUID

import pytest

from test_contract import (db, policy, clock, service, signal, restart, SlackFixture,
                           TENANT, PRIMARY, AuthenticatedEntity, rows, Incident, AlertAudit)


@pytest.fixture
def human():
    return AuthenticatedEntity(TENANT, PRIMARY, role='admin')


@pytest.fixture
def proof(clock):
    return {'type': 'business_reconciliation',
            'references': ['https://fixture.example.invalid/inventory/reconciliation/1'],
            'summary': 'Fixture operator reconciled committed stock effects against provider receipt.',
            'operation_scope': ['fixture-inventory-operation-1'], 'checked_at': clock()}


def acknowledged(service, clock, human):
    state = service.ingest(signal(clock))
    return service.acknowledge(state['incident_id'], human)


def test_authorized_business_closure_is_atomic_and_survives_restart(db, policy, service, clock, human, proof):
    state = acknowledged(service, clock, human)
    closed = service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    resumed = restart(db, policy, clock)
    durable = resumed.snapshot(state['incident_id'])
    assert durable['status'] == 'closed'
    incident = rows(resumed.engine, Incident)[0]
    assert incident['status'] == 'resolved'
    assert incident['end_time'] is not None
    audits = rows(resumed.engine, AlertAudit)
    assert len(audits) >= 2
    assert any(PRIMARY == audit['user_id'] and 'reconcil' in audit['description'].lower() for audit in audits)
    assert closed['revision'] > state['revision']


@pytest.mark.parametrize('evidence', [{}, {'queue_state': 'done'},
    {'type': 'business_reconciliation', 'references': [], 'summary': 'done'}])
def test_done_or_missing_proof_cannot_authorize_closure(service, clock, human, evidence):
    state = acknowledged(service, clock, human)
    with pytest.raises((ValueError, PermissionError)):
        service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=evidence)
    assert service.snapshot(state['incident_id'])['status'] == 'open'


def test_stale_revision_or_technical_actor_cannot_close(service, clock, human, proof):
    state = acknowledged(service, clock, human)
    technical = AuthenticatedEntity(TENANT, PRIMARY, role='admin', api_key_name='fixture-webhook')
    with pytest.raises((ValueError, PermissionError)):
        service.resolve(state['incident_id'], technical, expected_revision=state['revision'], evidence=proof)
    clock.advance(1)
    service.ingest(signal(clock, event_id='fixture-new-evidence'))
    with pytest.raises((ValueError, PermissionError)):
        service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    assert service.snapshot(state['incident_id'])['status'] == 'open'


def test_late_and_fresh_receipt_of_same_failure_cannot_reopen(service, clock, human, proof):
    original = signal(clock)
    state = service.ingest(original)
    state = service.acknowledge(state['incident_id'], human)
    service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    service.ingest(original)
    clock.advance(100)
    service.ingest(signal(clock, event_id='fixture-redelivery-with-new-intake-time'))
    durable = service.snapshot(state['incident_id'])
    assert durable['status'] == 'closed'
    notifier = SlackFixture()
    service.sweep(notifier)
    assert notifier.calls == []


def test_authorized_reopen_creates_new_generation_and_keeps_resolution_history(service, clock, human, proof):
    state = acknowledged(service, clock, human)
    closed = service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    reopened = service.reopen(state['incident_id'], human, expected_revision=closed['revision'],
                              reason='Fixture new occurrence independently reconciled by owner')
    assert reopened['incident_id'] == closed['incident_id']
    assert reopened['status'] == 'open'
    assert reopened['generation'] > closed['generation']
    assert reopened['history']
    with pytest.raises((ValueError, PermissionError)):
        service.reopen(state['incident_id'], human, expected_revision=closed['revision'], reason='stale request')


def test_closed_cases_do_not_starve_fresh_incident(service, clock, human, proof):
    state = acknowledged(service, clock, human)
    service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    fresh = service.ingest(signal(clock, job_uuid=str(UUID(int=221))))
    notifier = SlackFixture()
    for _ in range(2):
        service.sweep(notifier, limit=1)
    assert len(notifier.calls) == 1
    assert fresh['incident_id'] in notifier.calls[0][1]


def test_reopen_reuses_known_thread_and_preserves_prior_receipts(service, clock, human, proof):
    state = service.ingest(signal(clock))
    notifier = SlackFixture()
    state = service.dispatch(state['incident_id'], notifier)
    old_thread = state['thread_ts']
    state = service.acknowledge(state['incident_id'], human)
    state = service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    reopened = service.reopen(state['incident_id'], human, expected_revision=state['revision'], reason='Fixture independently confirmed recurrence')
    assert reopened['thread_ts'] == old_thread
    service.dispatch(state['incident_id'], notifier)
    assert len(notifier.calls) == 1  # known root retained, no duplicate initial post
    clock.advance(30)
    service.dispatch(state['incident_id'], notifier)
    assert notifier.calls[-1][2] == old_thread


def test_business_closure_cannot_hide_unknown_notification(service, clock, human, proof):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([TimeoutError('fixture unknown root receipt')])
    service.dispatch(state['incident_id'], notifier)
    state = service.acknowledge(state['incident_id'], human)
    with pytest.raises((ValueError, PermissionError)):
        service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    assert service.snapshot(state['incident_id'])['status'] == 'open'
    assert service.snapshot(state['incident_id'])['notifications']['initial']['status'] == 'unknown'


def test_late_slack_receipt_after_close_reopen_is_recorded_in_original_generation(service, clock, human, proof):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    entered, release = Event(), Event()
    class PausedNotifier(SlackFixture):
        def send(self, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().send(**kwargs)
    notifier = PausedNotifier()
    state = service.ingest(signal(clock))
    with ThreadPoolExecutor(max_workers=1) as workers:
        pending = workers.submit(service.dispatch, state['incident_id'], notifier)
        try:
            assert entered.wait(5)
            current = service.acknowledge(state['incident_id'], human)
            # Human fixture has independently found this exact external message.
            evidence = dict(proof, notification_reconciliation={
                'outcome': 'delivered', 'thread_ts': '1700000000.000001',
                'references': ['https://fixture.example.invalid/slack/confirmed-1'],
                'claim_ids': [current['notifications']['initial']['claim_id']]})
            closed = service.resolve(state['incident_id'], human, expected_revision=current['revision'], evidence=evidence)
            service.reopen(state['incident_id'], human, expected_revision=closed['revision'], reason='Fixture separately confirmed new occurrence')
        finally:
            release.set()
        pending.result(timeout=5)
    durable = service.snapshot(state['incident_id'])
    assert durable['history'][0]['notifications']['initial']['status'] == 'sent'
    assert durable['history'][0]['notifications']['initial']['receipt'] == '1700000000.000001'
    assert durable['generation'] == 2
    assert durable['thread_ts'] == '1700000000.000001'


@pytest.mark.parametrize('identity_mode,expected', [
    ('human', 200), ('api_key', 403), ('unapproved', 403), ('noauth', 403), ('impersonation', 403), ('done_only', 409)])
def test_resolution_http_boundary_trusts_authenticated_identity_only(db, policy, service, clock, human, proof,
                                                                    tmp_path, monkeypatch, identity_mode, expected):
    import json
    from dataclasses import asdict
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from keep.api.routes import incidents
    from keep.api.core import db as native_db
    state = acknowledged(service, clock, human)
    config = {'policy': asdict(policy), 'slack_provider_id': 'fixture-slack',
              'fallback_provider_id': 'fixture-independent', 'slack_targets': {
                  'primary': 'U00000001', 'backup': 'U00000002', 'incident_lead': 'U00000003'}}
    path = tmp_path / 'fixture-policy.json'
    path.write_text(json.dumps({'tenants': {TENANT: config}}))
    monkeypatch.setenv('INVENTORY_ATTENTION_POLICY_FILE', str(path))
    monkeypatch.setenv('AUTH_TYPE', 'noauth' if identity_mode == 'noauth' else 'db')
    monkeypatch.setenv('KEEP_IMPERSONATION_ENABLED', 'true' if identity_mode == 'impersonation' else 'false')
    monkeypatch.setattr(native_db, 'engine', db)
    actor = AuthenticatedEntity(TENANT, 'fixture-unapproved@example.invalid' if identity_mode == 'unapproved' else PRIMARY,
                                role='admin', api_key_name='fixture-key' if identity_mode == 'api_key' else None)
    app = FastAPI()
    app.include_router(incidents.router, prefix='/incidents')
    route = next(r for r in incidents.router.routes if r.path == '/{incident_id}/inventory/resolve')
    auth = next(d.call for d in route.dependant.dependencies if d.name == 'authenticated_entity')
    app.dependency_overrides[auth] = lambda: actor  # identity fixture, not a live IdP claim
    evidence = {'queue_state': 'done'} if identity_mode == 'done_only' else proof
    with TestClient(app) as client:
        response = client.post(f"/incidents/{state['incident_id']}/inventory/resolve", json={
            'expected_revision': state['revision'], 'evidence': evidence, 'actor': 'forged@example.invalid'})
    assert response.status_code == expected, response.text
    durable = service.snapshot(state['incident_id'])
    assert durable['status'] == ('closed' if expected == 200 else 'open')
    if expected == 200:
        assert durable['resolution']['actor'] == PRIMARY


def test_human_notification_reconciliation_preserves_original_unknown_audit(service, clock, human, proof):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([TimeoutError('fixture unknown root receipt')])
    service.dispatch(state['incident_id'], notifier)
    state = service.acknowledge(state['incident_id'], human)
    proof = dict(proof, notification_reconciliation={
        'outcome': 'delivered', 'thread_ts': '1700000000.000001',
        'references': ['https://fixture.example.invalid/slack/confirmed-1'],
        'claim_ids': [state['notifications']['initial']['claim_id']]})
    closed = service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=proof)
    assert closed['status'] == 'closed'
    assert closed['notifications']['initial']['status'] == 'unknown'  # human attestation distinct from transport receipt
    assert closed['resolution']['evidence']['notification_reconciliation']['outcome'] == 'delivered'
    reopened = service.reopen(state['incident_id'], human, expected_revision=closed['revision'], reason='Fixture independently confirmed recurrence')
    assert reopened['thread_ts'] == '1700000000.000001'
    assert reopened['history'][0]['notifications']['initial']['status'] == 'unknown'


def test_notification_proof_must_cover_independent_unknown_claim(service, policy, clock, human, proof):
    from test_delivery_attention import IndependentFixture
    notifier = IndependentFixture(TimeoutError('fixture independent confirmation lost'))
    state = service.ingest(signal(clock))
    service.dispatch(state['incident_id'], notifier)
    clock.advance(policy.reconciliation_seconds)
    service.sweep(notifier)
    state = service.acknowledge(state['incident_id'], human)
    incomplete = dict(proof, notification_reconciliation={
        'outcome': 'delivered', 'thread_ts': '1700000000.000001',
        'references': ['https://fixture.example.invalid/slack/confirmed-1'],
        'claim_ids': [state['notifications']['initial']['claim_id']]})
    assert state['attention']['fallback']['status'] == 'unknown'
    with pytest.raises(ValueError):
        service.resolve(state['incident_id'], human, expected_revision=state['revision'], evidence=incomplete)
    assert service.snapshot(state['incident_id'])['status'] == 'open'


def test_business_proof_must_cover_known_operation(service, clock, human, proof):
    state = acknowledged(service, clock, human)
    with pytest.raises(ValueError):
        service.resolve(state['incident_id'], human, expected_revision=state['revision'],
                        evidence=dict(proof, operation_scope=['fixture-other-operation']))
    assert service.snapshot(state['incident_id'])['status'] == 'open'
