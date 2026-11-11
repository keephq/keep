"""Independent attention for uncertain sends; no exactly-once delivery assumption."""
import pytest

from test_contract import (db, policy, clock, service, signal, restart, SlackFixture,
                           KnownNotDelivered, rows, Incident, LEAD)


class IndependentFixture(SlackFixture):
    def __init__(self, fallback_error=None):
        super().__init__([TimeoutError('fixture Slack receipt lost')])
        self.fallback_calls = []
        self.fallback_error = fallback_error

    def send_fallback(self, **kwargs):
        self.fallback_calls.append(kwargs)
        if self.fallback_error is not None:
            raise self.fallback_error
        return 'fixture-independent-durable-receipt-1'


@pytest.mark.parametrize('error,status', [
    (None, 'confirmed'),
    (KnownNotDelivered('fixture independent provider unavailable'), 'failed'),
    (TimeoutError('fixture independent response lost'), 'unknown'),
])
def test_unknown_slack_reaches_independent_attention_with_bounded_outcome(db, policy, service, clock, error, status):
    state = service.ingest(signal(clock))
    transport = IndependentFixture(error)
    uncertain = service.dispatch(state['incident_id'], transport)
    assert uncertain['notifications']['initial']['status'] == 'unknown'
    assert uncertain['attention']['status'] == 'reconciliation_required'
    assert uncertain['attention']['due_at'] == clock() + policy.reconciliation_seconds
    assert not transport.fallback_calls
    clock.advance(policy.reconciliation_seconds)
    service.sweep(transport)
    durable = service.snapshot(state['incident_id'])
    assert durable['attention']['status'] == 'manual_attention_required'
    assert durable['attention']['responsible'] == LEAD
    assert durable['attention']['fallback']['status'] == status
    assert rows(db, Incident)[0]['assignee'] == LEAD
    resumed = restart(db, policy, clock)
    clock.advance(100)
    for _ in range(2):
        resumed.sweep(transport)
    assert len(transport.calls) == 1
    assert len(transport.fallback_calls) == 1
    assert resumed.snapshot(state['incident_id'])['notifications']['initial']['status'] == 'unknown'


def test_fallback_crash_after_effect_is_unknown_and_not_replayed(db, policy, service, clock):
    class Crash(BaseException):
        pass
    transport = IndependentFixture(Crash('fixture independent acceptance then process loss'))
    state = service.ingest(signal(clock))
    service.dispatch(state['incident_id'], transport)
    clock.advance(policy.reconciliation_seconds)
    with pytest.raises(Crash):
        service.sweep(transport)
    assert service.snapshot(state['incident_id'])['attention']['fallback']['status'] == 'claimed'
    resumed = restart(db, policy, clock)
    clock.advance(policy.claim_timeout_seconds)
    resumed.sweep(transport)
    durable = resumed.snapshot(state['incident_id'])
    assert durable['attention']['fallback']['status'] == 'unknown'
    assert durable['attention']['status'] == 'manual_attention_required'
    assert len(transport.fallback_calls) == 1
