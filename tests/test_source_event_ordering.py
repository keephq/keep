"""Source-time admission; no AWS or notification delivery is performed."""

import copy
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from opentelemetry import trace
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from keep.api.core.source_event_ordering import source_event_decision
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert, LastAlert
from keep.api.models.db.tenant import Tenant
from keep.api.tasks import process_event_task as pipeline


def test_late_firing_cannot_replace_newer_recovery():
    previous = {"lastReceived": "2026-10-16T10:05:00Z", "status": "resolved"}
    incoming = {"lastReceived": "2026-10-16T10:00:00Z", "status": "firing"}
    assert source_event_decision(incoming, previous)["accepted"] is False


def test_interleaved_retry_cannot_reopen_episode():
    previous = {"lastReceived": "2026-10-16T10:05:00Z", "status": "resolved"}
    incoming = {"lastReceived": "2026-10-16T10:00:00Z", "status": "firing"}
    assert source_event_decision(incoming, previous)["reason"] == "older_source_event"


def test_recovery_requires_observed_episode():
    incoming = {"lastReceived": "2026-10-16T10:05:00Z", "status": "resolved"}
    assert source_event_decision(incoming, None)["recoveryEligible"] is False
    assert (
        source_event_decision(
            incoming, {"lastReceived": "2026-10-16T10:00:00Z", "status": "firing"}
        )["recoveryEligible"]
        is True
    )


def test_equal_time_conflict_is_not_ordered_by_arrival():
    previous = {"lastReceived": "2026-10-16T10:05:00Z", "status": "resolved"}
    incoming = {"lastReceived": "2026-10-16T10:05:00+00:00", "status": "firing"}
    assert (
        source_event_decision(incoming, previous)["reason"] == "conflicting_source_time"
    )


# Set this only to a disposable local PostgreSQL database. No Docker or external
# service is silently started, and no production credentials are used.
@pytest.fixture
def ordered_pipeline(monkeypatch):
    url = os.environ.get("KEEP_TEST_ORDERING_POSTGRES_URL")
    if not url:
        pytest.skip(
            "Set KEEP_TEST_ORDERING_POSTGRES_URL to an isolated PostgreSQL database"
        )
    engine = create_engine(url)
    schema = "source_ordering_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine.dispose()
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    SQLModel.metadata.create_all(
        engine, tables=[Tenant.__table__, Alert.__table__, LastAlert.__table__]
    )
    with Session(engine) as session:
        session.add(Tenant(id="tenant", name="isolated ordering test"))
        session.commit()
    queued = []
    disposed = []

    class Enrichments:
        def __init__(self, *args):
            pass

        def dispose_enrichments(self, fingerprint):
            disposed.append(fingerprint)

        def run_extraction_rules(self, event):
            return event

        def run_mapping_rules(self, event):
            pass

    monkeypatch.setenv("KEEP_SOURCE_EVENT_ORDERING_PROVIDERS", "cloudwatch")
    monkeypatch.setattr(pipeline, "EnrichmentsBl", Enrichments)
    for flag in [
        "KEEP_STORE_RAW_ALERTS",
        "KEEP_AUDIT_EVENTS_ENABLED",
        "KEEP_CALCULATE_START_FIRING_TIME_ENABLED",
        "KEEP_MAINTENANCE_WINDOWS_ENABLED",
        "KEEP_ALERT_FIELDS_ENABLED",
        "KEEP_CORRELATION_ENABLED",
    ]:
        monkeypatch.setattr(pipeline, flag, False)
    monkeypatch.setattr(pipeline, "get_started_at_for_alerts", lambda *a, **k: {})
    monkeypatch.setattr(pipeline, "get_enrichment_with_session", lambda **k: None)
    monkeypatch.setattr(pipeline, "enrich_alerts_with_incidents", lambda *a: [])
    monkeypatch.setattr(
        pipeline, "get_last_alert_hashes_by_fingerprints", lambda *a: {}
    )
    monkeypatch.setattr(
        pipeline,
        "AlertDeduplicator",
        lambda *a: SimpleNamespace(
            get_deduplication_rules=lambda **k: [],
            apply_deduplication=lambda event, *a: event,
        ),
    )
    monkeypatch.setattr(
        pipeline, "ElasticClient", lambda **k: SimpleNamespace(enabled=False)
    )
    monkeypatch.setattr(
        pipeline,
        "WorkflowManager",
        SimpleNamespace(
            get_instance=lambda: SimpleNamespace(
                insert_events=lambda tenant, events: queued.extend(
                    copy.deepcopy(events)
                )
            )
        ),
    )

    def receive(
        status,
        minute,
        fingerprint="alarm",
        timestamp_forced=None,
        provider_id="provider",
    ):
        event = AlertDto(
            name="isolated",
            fingerprint=fingerprint,
            status=status,
            lastReceived=f"2026-10-16T10:{minute:02}:00Z",
            source=["cloudwatch"],
            alert_hash="test",
            isFullDuplicate=False,
        )
        with Session(engine) as session:
            return pipeline.__handle_formatted_events(
                "tenant",
                "cloudwatch",
                session,
                [],
                [event],
                trace.get_tracer(__name__),
                provider_id,
                False,
                timestamp_forced,
            )

    yield engine, receive, queued, disposed
    engine.dispose()
    cleanup = create_engine(url)
    with cleanup.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    cleanup.dispose()


def test_pipeline_archives_late_alarm_without_current_state_effects(ordered_pipeline):
    engine, receive, queued, disposed = ordered_pipeline
    before_ingest = datetime.now(timezone.utc).replace(tzinfo=None)
    receive("resolved", 5)
    receive("firing", 0)
    after_ingest = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine) as session:
        current = session.exec(
            select(Alert).join(LastAlert, LastAlert.alert_id == Alert.id)
        ).one()
        history = session.exec(select(Alert)).all()
        assert current.event["status"] == "resolved"
        assert len(history) == 2
        assert sorted(
            row.event["sourceEventOrdering"]["accepted"] for row in history
        ) == [False, True]
        assert all(before_ingest <= row.timestamp <= after_ingest for row in history)
    assert len(queued) == len(disposed) == 1
    assert queued[0].sourceEventOrdering["recoveryEligible"] is False


def test_pipeline_preserves_episode_and_rejects_interleaved_retry(ordered_pipeline):
    engine, receive, queued, disposed = ordered_pipeline
    receive("firing", 0)
    receive("pending", 2)
    receive("resolved", 5)
    receive("firing", 0)
    assert len(queued) == len(disposed) == 3
    assert queued[-1].sourceEventOrdering["recoveryEligible"] is True
    assert queued[-1].sourceEventOrdering["eventId"] == queued[-1].event_id


def test_concurrent_first_events_converge_to_latest_source_time(ordered_pipeline):
    engine, receive, queued, disposed = ordered_pipeline
    start = threading.Barrier(2)

    def run(status, minute):
        start.wait(timeout=5)
        return receive(status, minute)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, "firing", 0), pool.submit(run, "resolved", 5)]
        for future in futures:
            future.result(timeout=15)
    with Session(engine) as session:
        current = session.exec(
            select(Alert).join(LastAlert, LastAlert.alert_id == Alert.id)
        ).one()
        assert current.event["status"] == "resolved"
        assert len(session.exec(select(LastAlert)).all()) == 1
        assert len(session.exec(select(Alert)).all()) == 2


def test_opt_in_rejects_unsupported_database(monkeypatch):
    from keep.api.core.source_event_ordering import serialized_source_event

    with pytest.raises(ValueError, match="PostgreSQL"):
        with serialized_source_event(create_engine("sqlite://"), "tenant", "alarm"):
            pytest.fail("Unsupported backend must fail before mutation")


def test_late_recovery_cannot_resolve_newer_firing(ordered_pipeline):
    engine, receive, queued, disposed = ordered_pipeline
    receive("firing", 5)
    receive("resolved", 0)
    with Session(engine) as session:
        current = session.exec(
            select(Alert).join(LastAlert, LastAlert.alert_id == Alert.id)
        ).one()
        assert current.event["status"] == "firing"
    assert len(queued) == len(disposed) == 1


def test_exact_retry_and_equal_time_conflict_are_archived(ordered_pipeline):
    engine, receive, queued, disposed = ordered_pipeline
    receive("firing", 5)
    receive("firing", 5)
    receive("resolved", 5)
    with Session(engine) as session:
        history = session.exec(select(Alert)).all()
        assert {row.event["sourceEventOrdering"]["reason"] for row in history} == {
            "accepted",
            "duplicate_source_event",
            "conflicting_source_time",
        }
    assert len(queued) == len(disposed) == 1


def test_newer_full_duplicate_still_advances_source_cursor(
    ordered_pipeline, monkeypatch
):
    engine, receive, queued, disposed = ordered_pipeline

    def mark_duplicate(event, *args):
        event.isFullDuplicate = True
        return event

    monkeypatch.setattr(
        pipeline,
        "AlertDeduplicator",
        lambda *a: SimpleNamespace(
            get_deduplication_rules=lambda **k: [], apply_deduplication=mark_duplicate
        ),
    )
    receive("firing", 0)
    receive("firing", 5)
    receive("resolved", 2)
    with Session(engine) as session:
        current = session.exec(
            select(Alert).join(LastAlert, LastAlert.alert_id == Alert.id)
        ).one()
        assert current.event["status"] == "firing"
        assert current.event["lastReceived"].startswith("2026-10-16T10:05")
    assert len(queued) == 2


def test_extraction_and_mapping_cannot_replace_ordering_context(
    ordered_pipeline, monkeypatch
):
    engine, receive, queued, disposed = ordered_pipeline

    class AdversarialEnrichment:
        def __init__(self, *args):
            pass

        def dispose_enrichments(self, *args):
            pass

        def run_extraction_rules(self, event):
            event.sourceEventOrdering = {"accepted": False, "recoveryEligible": True}
            return event

        def run_mapping_rules(self, event):
            event.sourceEventOrdering = {"accepted": False, "recoveryEligible": True}

    monkeypatch.setattr(pipeline, "EnrichmentsBl", AdversarialEnrichment)
    receive("resolved", 5)
    assert queued[0].sourceEventOrdering["accepted"] is True
    assert queued[0].sourceEventOrdering["recoveryEligible"] is False
    with Session(engine) as session:
        stored = session.exec(select(Alert)).one()
        assert stored.event["sourceEventOrdering"]["accepted"] is True
        assert stored.event["sourceEventOrdering"]["recoveryEligible"] is False


def test_other_providers_do_not_enter_ordering(monkeypatch):
    from keep.api.core.source_event_ordering import enabled

    monkeypatch.setenv("KEEP_SOURCE_EVENT_ORDERING_PROVIDERS", "cloudwatch,grafana")
    assert enabled("cloudwatch")
    assert not enabled("grafana")
    monkeypatch.delenv("KEEP_SOURCE_EVENT_ORDERING_PROVIDERS")
    assert not enabled("cloudwatch")


def test_naive_source_time_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        source_event_decision(
            {"lastReceived": "2026-10-16T10:00:00", "status": "firing"}, None
        )


def test_fingerprint_lock_survives_commits_without_blocking_other_alarms(
    ordered_pipeline,
):
    from keep.api.core.source_event_ordering import serialized_source_event

    engine, _, _, _ = ordered_pipeline
    held = threading.Event()
    release = threading.Event()
    waiting = threading.Event()
    admitted = threading.Event()

    def hold():
        with serialized_source_event(engine, "tenant", "one") as session:
            session.exec(text("SELECT 1"))
            session.commit()
            held.set()
            assert release.wait(timeout=5)

    def same_fingerprint():
        waiting.set()
        with serialized_source_event(engine, "tenant", "one"):
            admitted.set()

    def other_fingerprint():
        with serialized_source_event(engine, "tenant", "two"):
            return True

    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(hold)
        assert held.wait(timeout=5)
        second = pool.submit(same_fingerprint)
        try:
            assert waiting.wait(timeout=5)
            assert not admitted.wait(timeout=0.1)
            assert pool.submit(other_fingerprint).result(timeout=5)
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert admitted.is_set()


def test_fingerprint_lock_is_released_after_failure(ordered_pipeline):
    from keep.api.core.source_event_ordering import serialized_source_event

    engine, _, _, _ = ordered_pipeline
    with pytest.raises(RuntimeError, match="local failure"):
        with serialized_source_event(engine, "tenant", "one"):
            raise RuntimeError("local failure")
    with ThreadPoolExecutor(max_workers=1) as pool:

        def retry():
            with serialized_source_event(engine, "tenant", "one"):
                return True

        assert pool.submit(retry).result(timeout=5)


def test_source_ordering_is_independent_of_ingestion_clock(ordered_pipeline):
    engine, receive, queued, _ = ordered_pipeline
    receive("firing", 0, timestamp_forced=datetime(2026, 10, 16, 11))
    receive("resolved", 5, timestamp_forced=datetime(2026, 10, 16, 10))
    with Session(engine) as session:
        current = session.exec(
            select(Alert).join(LastAlert, LastAlert.alert_id == Alert.id)
        ).one()
        assert current.event["status"] == "resolved"
        assert current.timestamp == datetime(2026, 10, 16, 10)


def test_post_format_enrichments_cannot_redirect_admitted_fingerprint(
    ordered_pipeline, monkeypatch
):
    engine, receive, queued, disposed = ordered_pipeline

    class IdentityChangingEnrichment:
        def __init__(self, *args):
            pass

        def dispose_enrichments(self, fingerprint):
            disposed.append(fingerprint)

        def run_extraction_rules(self, event):
            event.fingerprint = "different-entity"
            return event

        def run_mapping_rules(self, event):
            event.fingerprint = "different-mapping-entity"

    monkeypatch.setattr(pipeline, "EnrichmentsBl", IdentityChangingEnrichment)
    receive("firing", 5)
    receive("resolved", 0)
    with Session(engine) as session:
        cursor = session.exec(select(LastAlert)).one()
        current = session.get(Alert, cursor.alert_id)
        assert cursor.fingerprint == current.fingerprint == "alarm"
        assert current.event["status"] == "firing"
        assert len(session.exec(select(Alert)).all()) == 2
    assert [event.fingerprint for event in queued] == ["alarm"]
    assert disposed == ["alarm"]


@pytest.mark.parametrize("conflict", ["provider_id", "provider_type"])
def test_existing_cursor_from_another_provider_is_rejected_before_mutation(
    ordered_pipeline, conflict
):
    engine, receive, queued, disposed = ordered_pipeline
    receive("firing", 5)
    with Session(engine) as session:
        initial = session.exec(select(Alert)).one()
        setattr(initial, conflict, "another-provider")
        session.add(initial)
        session.commit()
    with pytest.raises(ValueError, match="provider identity"):
        receive("resolved", 6)
    with Session(engine) as session:
        assert len(session.exec(select(Alert)).all()) == 1
        cursor = session.exec(select(LastAlert)).one()
        assert session.get(Alert, cursor.alert_id).event["status"] == "firing"
    assert len(queued) == len(disposed) == 1


@pytest.mark.parametrize("protect", [True, False])
def test_actual_extraction_filters_reserved_fields_before_persisting(
    protect, monkeypatch
):
    from unittest.mock import Mock

    from keep.api.bl.enrichments_bl import EnrichmentsBl
    from keep.api.models.db.extraction import ExtractionRule

    monkeypatch.setattr(EnrichmentsBl, "ENRICHMENT_DISABLED", False)
    bl = object.__new__(EnrichmentsBl)
    bl.tenant_id = "tenant"
    bl._add_enrichment_log = Mock()
    bl._track_enrichment_event = Mock()
    bl.enrich_entity = Mock()
    if protect:
        bl.protected_fields = {"fingerprint", "sourceEventOrdering"}
    event = AlertDto(
        name="isolated",
        fingerprint="alarm",
        status="firing",
        lastReceived="2026-10-16T10:00:00Z",
        message="different-entity|spoofed|payments",
        sourceEventOrdering={"accepted": True},
    )
    rule = ExtractionRule(
        id=1,
        tenant_id="tenant",
        name="identity-rewrite",
        attribute="message",
        regex=r"(?P<fingerprint>[^|]+)\|(?P<sourceEventOrdering>[^|]+)\|(?P<service>.+)",
    )
    result = bl.run_extraction_rules(event, rules=[rule])
    persisted = bl.enrich_entity.call_args.args[1]
    assert result.service == persisted["service"] == "payments"
    if protect:
        assert result.fingerprint == "alarm"
        assert result.sourceEventOrdering == {"accepted": True}
        assert persisted == {"service": "payments"}
    else:
        assert result.fingerprint == persisted["fingerprint"] == "different-entity"


@pytest.mark.parametrize("protect", [True, False])
def test_actual_mapping_filters_reserved_fields_before_persisting(protect):
    from unittest.mock import Mock

    from keep.api.bl.enrichments_bl import EnrichmentsBl
    from keep.api.models.db.mapping import MappingRule

    bl = object.__new__(EnrichmentsBl)
    bl.tenant_id = "tenant"
    bl._add_enrichment_log = Mock()
    bl._track_enrichment_event = Mock()
    bl.enrich_entity = Mock()
    if protect:
        bl.protected_fields = {"fingerprint", "sourceEventOrdering"}
    event = AlertDto(
        name="isolated",
        fingerprint="alarm",
        status="firing",
        lastReceived="2026-10-16T10:00:00Z",
        sourceEventOrdering={"accepted": True},
    )
    rule = MappingRule(
        id=1,
        tenant_id="tenant",
        name="identity-rewrite",
        type="csv",
        matchers=[["name"]],
        rows=[
            {
                "name": "^isolated$",
                "fingerprint": "different-entity",
                "sourceEventOrdering": {"accepted": False},
                "service": "payments",
            }
        ],
    )
    assert bl.check_if_match_and_enrich(event, rule) is True
    persisted = bl.enrich_entity.call_args.args[1]
    assert event.service == persisted["service"] == "payments"
    if protect:
        assert event.fingerprint == "alarm"
        assert event.sourceEventOrdering == {"accepted": True}
        assert bl.enrich_entity.call_args.args[0] == "alarm"
        assert persisted == {"service": "payments"}
    else:
        assert event.fingerprint == persisted["fingerprint"] == "different-entity"


def test_persisted_enrichments_cannot_override_admitted_identity(
    ordered_pipeline, monkeypatch
):
    _, receive, queued, _ = ordered_pipeline
    monkeypatch.setattr(
        pipeline,
        "get_enrichment_with_session",
        lambda **kwargs: SimpleNamespace(
            enrichments={
                "fingerprint": "foreign-entity",
                "sourceEventOrdering": {"accepted": False},
                "service": "payments",
            }
        ),
    )
    receive("firing", 5)
    assert queued[0].fingerprint == "alarm"
    assert queued[0].sourceEventOrdering["accepted"] is True
    assert queued[0].service == "payments"
