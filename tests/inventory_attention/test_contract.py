"""Local contract fixtures: synthetic actors/times/destinations, never operational policy.

The service and Keep's native tables are real. Only the clock and outbound Slack
boundary are fixtures. File-backed SQLite is closed and reopened for restarts.
No credentials, network calls, live alerts or real messages are used.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import make_url

from keep.api.bl.inventory_attention import (
    InventoryAttentionService,
    KnownNotDelivered,
    Policy,
    create_test_schema,
)
from keep.api.models.db.alert import AlertAudit, AlertEnrichment
from keep.api.models.db.incident import Incident
from keep.api.models.db.tenant import Tenant
from keep.identitymanager.authenticatedentity import AuthenticatedEntity


TENANT = "fixture-tenant-not-production"
JOB = "11111111-1111-4111-8111-111111111111"
GRAPH = "22222222-2222-4222-8222-222222222222"
PRIMARY = "fixture-primary@example.invalid"
BACKUP = "fixture-backup@example.invalid"
LEAD = "fixture-lead@example.invalid"


class Clock:
    def __init__(self):
        self.value = 1_700_000_000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class SlackFixture:
    """Persisted external receipts are intentionally independent of DB state."""

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls = []
        self.receipts = []

    def send(self, transition, text, thread_ts, idempotency_key):
        self.calls.append((transition, text, thread_ts, idempotency_key))
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure
        receipt = thread_ts or "1700000000.000001"
        self.receipts.append((transition, receipt))
        return receipt


@pytest.fixture
def policy():
    return Policy(
        policy_id="fixture-seven-day-pilot-NOT-approved",
        enabled=True,
        shared_channel="FIXTURE-CHANNEL-NOT-SLACK",
        primary=PRIMARY,
        backup=BACKUP,
        incident_lead=LEAD,
        primary_after_seconds=30,
        ack_seconds=10,
        claim_timeout_seconds=5,
        max_notification_attempts=3,
        allowed_humans=(PRIMARY, BACKUP, LEAD),
        coverage="fixture-only; no operational coverage implied",
        closure_policy="fixture: no automatic closure; verified business evidence required",
    )


@pytest.fixture
def db(tmp_path):
    configured = os.environ.get("KEEP_INVENTORY_TEST_PG_URL")
    admin = None
    schema = None
    if configured:
        url = make_url(configured)
        if (url.host != "127.0.0.1" or not url.database.startswith("inventory_attention_fixture_")
                or url.port in (None, 5432)):
            raise RuntimeError("Refusing a database outside the explicitly isolated fixture contract")
        admin = create_engine(url, connect_args={"connect_timeout": 5})
        schema = "inventory_fixture_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = url.update_query_dict({"options": f"-csearch_path={schema}"})
        engine = fresh_engine(url)
    else:
        engine = fresh_engine(f"sqlite:///{tmp_path / 'native-keep-contract.sqlite'}")
    create_test_schema(engine)
    with engine.begin() as connection:
        connection.execute(insert(Tenant.__table__).values(id=TENANT, name="Fixture"))
    yield engine
    engine.dispose()
    if admin:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def service(db, policy, clock):
    return InventoryAttentionService(db, TENANT, policy, clock=clock)


def signal(clock, **changes):
    value = {
        "event_id": "fixture-observation-1",
        "observed_at": clock(),
        "kind": "parent_failed",
        "channel": "root.inventory_orchestrator",
        "job_uuid": JOB,
        "graph_uuid": GRAPH,
        "operation_id": "fixture-inventory-operation-1",
        "evidence": {"queue_state": "failed", "source": "fixture-read-only-snapshot"},
    }
    value.update(changes)
    return value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__)).mappings().all()


def fresh_engine(url):
    parsed = make_url(url)
    arguments = {"timeout": 10, "check_same_thread": False} if parsed.get_backend_name() == "sqlite" else {"connect_timeout": 5}
    return create_engine(parsed, connect_args=arguments)


def restart(db, policy, clock):
    url = db.url
    db.dispose()
    reopened = fresh_engine(url)
    return InventoryAttentionService(reopened, TENANT, policy, clock=clock)


def test_failed_inventory_without_retry_telemetry_creates_one_native_incident(service, db, clock):
    observation = signal(clock)  # deliberately no A1 retry cause event
    first = service.ingest(observation)
    again = service.ingest(observation)

    assert again["incident_id"] == first["incident_id"]
    incidents = rows(db, Incident)
    assert len(incidents) == 1
    assert str(incidents[0]["id"]) == first["incident_id"]
    assert incidents[0]["status"] == "firing"
    assert incidents[0]["resolve_on"] == "never"
    assert len(rows(db, AlertEnrichment)) == 1


def test_old_redelivery_cannot_renew_deadline_or_create_second_thread(service, clock):
    initial = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(initial["incident_id"], notifier)
    clock.advance(20)
    service.ingest(signal(clock, event_id="older", observed_at=clock() - 100))
    service.dispatch(initial["incident_id"], notifier)

    current = service.snapshot(initial["incident_id"])
    assert current["primary_due_at"] == initial["primary_due_at"]
    assert current["last_observed_at"] == initial["last_observed_at"]
    assert len(notifier.calls) == 1


def test_restart_keeps_incident_thread_and_deadlines(db, policy, service, clock):
    original = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(original["incident_id"], notifier)
    restored = restart(db, policy, clock)
    same = restored.ingest(signal(clock))
    restored.dispatch(same["incident_id"], notifier)
    assert same["incident_id"] == original["incident_id"]
    assert same["primary_due_at"] == original["primary_due_at"]
    assert len(notifier.calls) == 1


def test_missing_correlations_remain_explicit_not_guessed(service, clock):
    state = service.ingest(signal(clock, graph_uuid=None, operation_id=None, evidence={}))
    assert "graph_uuid" in state["missing"]
    assert "operation_id" in state["missing"]
    assert state["ack"] is None
    assert state.get("recovery_authorized", False) is False


def test_known_not_delivered_can_retry_within_budget(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([KnownNotDelivered("fixture rejected before send"), None])
    service.dispatch(state["incident_id"], notifier)
    service.sweep(notifier)
    assert len(notifier.calls) == 2
    assert len(notifier.receipts) == 1


def test_ambiguous_slack_outcome_survives_restart_without_blind_resend(db, policy, service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([TimeoutError("fixture acknowledgement lost")])
    service.dispatch(state["incident_id"], notifier)
    restored = restart(db, policy, clock)
    clock.advance(100)
    restored.sweep(notifier)
    current = restored.snapshot(state["incident_id"])
    assert current["notifications"]["initial"]["status"] == "unknown"
    assert len(notifier.calls) == 1


def test_api_key_is_not_human_ack(service, clock):
    state = service.ingest(signal(clock))
    technical_actor = AuthenticatedEntity(TENANT, PRIMARY, api_key_name="fixture-webhook")
    with pytest.raises((ValueError, PermissionError)):
        service.acknowledge(state["incident_id"], technical_actor)
    assert service.snapshot(state["incident_id"])["ack"] is None


def test_human_ack_is_durable_and_stops_future_pages(db, policy, service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(state["incident_id"], notifier)
    actor = AuthenticatedEntity(TENANT, PRIMARY, role="admin")
    service.acknowledge(state["incident_id"], actor)
    restored = restart(db, policy, clock)
    clock.advance(100)
    restored.sweep(notifier)
    assert restored.snapshot(state["incident_id"])["ack"]["actor"] == PRIMARY
    assert len(notifier.calls) == 1
    incidents = rows(restored.engine, Incident)
    assert incidents[0]["status"] == "acknowledged"
    assert incidents[0]["assignee"] == PRIMARY
    assert rows(restored.engine, AlertAudit)


def test_no_ack_escalates_once_per_transition(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(state["incident_id"], notifier)
    clock.advance(30)
    service.sweep(notifier)
    service.sweep(notifier)
    assert [call[0] for call in notifier.calls] == ["initial", "primary"]
    clock.advance(10)
    service.sweep(notifier)
    service.sweep(notifier)
    assert [call[0] for call in notifier.calls] == ["initial", "primary", "backup"]
    assert all(call[2] == "1700000000.000001" for call in notifier.calls[1:])
    assert len({call[3] for call in notifier.calls}) == 3


def test_recovery_or_done_evidence_does_not_close_incident(service, db, clock):
    state = service.ingest(signal(clock))
    clock.advance(1)
    service.ingest(signal(clock, event_id="fixture-resolved", kind="recovery", evidence={"queue_state": "done", "operation_state": "done"}))
    assert service.snapshot(state["incident_id"])["ack"] is None
    assert rows(db, Incident)[0]["status"] == "firing"


def test_two_workers_cannot_create_two_native_incidents(db, policy, clock):
    def ingest_once(_):
        worker = InventoryAttentionService(db, TENANT, policy, clock=clock)
        return worker.ingest(signal(clock))["incident_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        identifiers = list(pool.map(ingest_once, range(8)))
    assert len(set(identifiers)) == 1
    assert len(rows(db, Incident)) == 1


def test_disabled_policy_does_not_send(service, policy, db, clock):
    inactive = InventoryAttentionService(db, TENANT, replace(policy, enabled=False), clock=clock)
    notifier = SlackFixture()
    inactive.sweep(notifier)
    assert inactive.ingest(signal(clock))["status"] == "disabled"
    assert notifier.calls == []
    assert rows(db, Incident) == []


def test_ambiguous_primary_page_still_has_ack_deadline_and_backup_once(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([None, TimeoutError("fixture primary result unknown"), None])
    service.dispatch(state["incident_id"], notifier)
    clock.advance(30)
    service.sweep(notifier)
    assert service.snapshot(state["incident_id"])["notifications"]["primary"]["status"] == "unknown"
    clock.advance(10)
    service.sweep(notifier)
    service.sweep(notifier)
    assert [call[0] for call in notifier.calls] == ["initial", "primary", "backup"]
    assert service.snapshot(state["incident_id"])["notifications"]["primary"]["status"] == "unknown"


def test_source_only_evidence_is_not_complete(service, clock):
    state = service.ingest(signal(clock, evidence={"source": "fixture-db"}))
    assert {"evidence.captured_at", "evidence.queue_state", "evidence.completeness"}.issubset(set(state["missing"]))


def test_crash_after_slack_effect_before_receipt_preserves_unknown_on_restart(db, policy, service, clock):
    class ProcessCrash(BaseException):
        pass

    class SlackEffectThenCrash(SlackFixture):
        def send(self, *args, **kwargs):
            super().send(*args, **kwargs)
            raise ProcessCrash("fixture process dies after external effect")

    state = service.ingest(signal(clock))
    notifier = SlackEffectThenCrash()
    with pytest.raises(ProcessCrash):
        service.dispatch(state["incident_id"], notifier)
    assert notifier.receipts == [("initial", "1700000000.000001")]
    restored = restart(db, policy, clock)
    clock.advance(6)
    restored.sweep(notifier)
    assert restored.snapshot(state["incident_id"])["notifications"]["initial"]["status"] == "unknown"
    assert len(notifier.calls) == 1


def test_concurrent_sweeps_claim_primary_transition_once(db, policy, service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.dispatch(state["incident_id"], notifier)
    clock.advance(30)

    def sweep_once(_):
        worker = InventoryAttentionService(db, TENANT, policy, clock=clock)
        worker.sweep(notifier)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(sweep_once, range(8)))
    assert [call[0] for call in notifier.calls] == ["initial", "primary"]


def test_notification_retry_budget_exhaustion_stops_external_attempts(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([KnownNotDelivered("fixture rejected")] * 5)
    for _ in range(6):
        service.sweep(notifier)
    current = service.snapshot(state["incident_id"])
    assert len(notifier.calls) == 3
    assert current["notifications"]["initial"]["status"] == "exhausted"
    assert current["status"] == "open"


def test_ack_from_wrong_tenant_or_unapproved_human_is_rejected(service, db, clock):
    state = service.ingest(signal(clock))
    for actor in (
        AuthenticatedEntity("other-fixture-tenant", PRIMARY, role="admin"),
        AuthenticatedEntity(TENANT, "unapproved@example.invalid", role="admin"),
    ):
        with pytest.raises((PermissionError, ValueError)):
            service.acknowledge(state["incident_id"], actor)
    assert service.snapshot(state["incident_id"])["ack"] is None
    assert rows(db, AlertAudit) == []


def test_duplicate_human_ack_preserves_first_owner_and_audit(service, db, clock):
    state = service.ingest(signal(clock))
    service.acknowledge(state["incident_id"], AuthenticatedEntity(TENANT, PRIMARY, role="admin"))
    clock.advance(10)
    service.acknowledge(state["incident_id"], AuthenticatedEntity(TENANT, BACKUP, role="admin"))
    current = service.snapshot(state["incident_id"])
    assert current["ack"]["actor"] == PRIMARY
    assert len(rows(db, AlertAudit)) == 1


def test_no_progress_without_durable_clocks_becomes_coverage_unknown(service, clock):
    state = service.ingest(signal(clock, kind="no_progress"))
    assert state["kind"] == "coverage_unknown"
    assert {"accepted_at", "last_verified_success_at"}.issubset(set(state["missing"]))
    assert state.get("recovery_authorized", False) is False


def test_missing_job_uses_explicit_source_identity_not_string_none(service, db, clock):
    first = service.ingest(signal(clock, kind="coverage_unknown", job_uuid=None,
                                  source_fingerprint="fixture-source-a"))
    second = service.ingest(signal(clock, kind="coverage_unknown", job_uuid=None,
                                   source_fingerprint="fixture-source-b"))
    assert first["incident_id"] != second["incident_id"]
    assert "job_uuid" in first["missing"]
    assert len(rows(db, Incident)) == 2


def test_primary_known_failure_exhaustion_still_reaches_backup(service, clock):
    state = service.ingest(signal(clock))
    notifier = SlackFixture([None] + [KnownNotDelivered("fixture no page sent")] * 3 + [None])
    service.dispatch(state["incident_id"], notifier)
    clock.advance(30)
    for _ in range(4):
        service.sweep(notifier)
    clock.advance(10)
    service.sweep(notifier)
    service.sweep(notifier)
    assert [call[0] for call in notifier.calls] == ["initial", "primary", "primary", "primary", "backup"]
    assert service.snapshot(state["incident_id"])["notifications"]["primary"]["status"] == "exhausted"


def test_other_policies_cannot_starve_current_policy_sweep(db, policy, service, clock):
    other = InventoryAttentionService(db, TENANT, replace(policy, policy_id="other-fixture-policy"), clock=clock)
    other.ingest(signal(clock))
    other.ingest(signal(clock, job_uuid="33333333-3333-4333-8333-333333333333"))
    current = service.ingest(signal(clock))
    notifier = SlackFixture()
    service.sweep(notifier, limit=2)
    assert len(notifier.calls) == 1
    assert current["incident_id"] in notifier.calls[0][1]


@pytest.mark.parametrize("invalid", [True, 123, ["not-an-id"], {"id": JOB}])
def test_untrusted_identity_is_not_coerced_to_string(service, clock, invalid):
    with pytest.raises(ValueError):
        service.ingest(signal(clock, job_uuid=invalid))


def test_overlong_source_identity_is_rejected_not_truncated_into_collision(service, clock):
    with pytest.raises(ValueError):
        service.ingest(signal(clock, kind="coverage_unknown", job_uuid=None,
                              source_fingerprint="x" * 300))


def test_missing_all_stable_identity_is_rejected_not_randomly_invented(service, clock):
    with pytest.raises(ValueError):
        service.ingest(signal(clock, job_uuid=None, source_fingerprint=None))


def test_restart_policy_drift_under_same_id_requires_explicit_migration(service, policy, clock):
    state = service.ingest(signal(clock))
    changed = replace(policy, primary=BACKUP, primary_after_seconds=1)
    restarted = InventoryAttentionService(service.engine, TENANT, changed, clock=clock)
    slack = SlackFixture()
    with pytest.raises(ValueError, match="Policy changed"):
        restarted.dispatch(state['incident_id'], slack)
    assert not slack.calls
    assert service.snapshot(state['incident_id'])['applied_policy']['primary'] == PRIMARY
