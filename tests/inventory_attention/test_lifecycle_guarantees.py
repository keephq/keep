"""Failure-boundary contracts. All actors, clocks and transports are fixtures."""
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from test_contract import (db, policy, clock, service, signal, restart, SlackFixture,
                           TENANT, PRIMARY, AuthenticatedEntity)


def test_ack_committed_before_claim_prevents_page(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(state['incident_id'], notifier)
    clock.advance(30)
    service.acknowledge(state['incident_id'], AuthenticatedEntity(TENANT, PRIMARY, role='admin'))
    service.dispatch(state['incident_id'], notifier)
    assert [call[0] for call in notifier.calls] == ['initial']


def test_ack_after_claim_preserves_owner_and_only_already_authorized_page(service, clock):
    """Claim is send authorization point; a later ACK cannot retract network I/O."""
    entered, release = Event(), Event()

    class PausedNotifier(SlackFixture):
        def send(self, **kwargs):
            if kwargs['transition'] == 'primary':
                entered.set()
                assert release.wait(5), 'fixture release missing'
            return super().send(**kwargs)

    notifier = PausedNotifier()
    state = service.ingest(signal(clock))
    service.dispatch(state['incident_id'], notifier)
    clock.advance(30)
    with ThreadPoolExecutor(max_workers=1) as workers:
        sending = workers.submit(service.dispatch, state['incident_id'], notifier)
        try:
            assert entered.wait(5), 'primary claim was not reached'
            acknowledged = service.acknowledge(state['incident_id'], AuthenticatedEntity(TENANT, PRIMARY, role='admin'))
            assert acknowledged['notifications']['primary']['status'] == 'claimed'
        finally:
            release.set()
        sending.result(timeout=5)
    clock.advance(100)
    service.sweep(notifier)
    durable = service.snapshot(state['incident_id'])
    assert durable['ack']['actor'] == PRIMARY
    assert [call[0] for call in notifier.calls] == ['initial', 'primary']
    assert durable['notifications']['primary']['status'] == 'sent'


def test_crash_after_claim_before_send_is_unknown_without_blind_retry(db, policy, service, clock):
    state = service.ingest(signal(clock))
    assert service._claim(state['incident_id']) is not None
    # No send took place, but the restarted process cannot establish that fact.
    resumed = restart(db, policy, clock)
    notifier = SlackFixture()
    clock.advance(6)
    resumed.sweep(notifier)
    durable = resumed.snapshot(state['incident_id'])
    assert durable['notifications']['initial']['status'] == 'unknown'
    assert notifier.calls == []


def test_bounded_sweep_rotates_past_unknown_incidents_after_restart(db, policy, service, clock):
    identifiers = []
    for i in range(5):
        state = service.ingest(signal(clock, job_uuid=str(UUID(int=i + 10))))
        identifiers.append(state['incident_id'])
        service._claim(state['incident_id'])
    fresh = service.ingest(signal(clock, job_uuid=str(UUID(int=99))))
    resumed = restart(db, policy, clock)
    notifier = SlackFixture()
    clock.advance(6)
    for _ in range(6):
        assert len(resumed.sweep(notifier, limit=1)) <= 1
    assert len(notifier.calls) == 1
    assert fresh['incident_id'] in notifier.calls[0][1]
    for incident_id in identifiers:
        assert resumed.snapshot(incident_id)['notifications']['initial']['status'] == 'unknown'


def test_corrupt_policy_row_cannot_abort_sweep_or_starve_new_case(service, db, clock):
    from sqlalchemy import update
    from keep.api.models.db.alert import AlertEnrichment
    old = service.ingest(signal(clock))
    corrupted = dict(old, policy_digest='fixture-corruption-no-valid-policy')
    with db.begin() as connection:
        connection.execute(update(AlertEnrichment.__table__).where(
            AlertEnrichment.alert_fingerprint == service._key(old['incident_id'])
        ).values(enrichments=corrupted))
    fresh = service.ingest(signal(clock, job_uuid=str(UUID(int=120))))
    notifier = SlackFixture()
    # An invalid first case must produce a bounded diagnostic result and rotate;
    # it must not abort the whole workflow or leave later incidents unattended.
    for _ in range(2):
        service.sweep(notifier, limit=1)
    assert len(notifier.calls) == 1
    assert fresh['incident_id'] in notifier.calls[0][1]
