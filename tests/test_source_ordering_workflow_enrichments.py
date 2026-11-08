"""Real workflow admission/retry boundaries with isolated DB and inert execution."""

import copy
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from keep.api.core import db
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert, LastAlert
from keep.api.models.db.tenant import Tenant
from keep.workflowmanager import workflowmanager as manager_module
from keep.workflowmanager import workflowscheduler as scheduler_module


def alert_event():
    return AlertDto(
        name="isolated workflow regression",
        fingerprint="admitted-alarm",
        source=["cloudwatch"],
        providerType="cloudwatch",
        providerId="provider",
        status="resolved",
        severity="info",
        lastReceived="2026-10-18T10:05:00Z",
        event_id="d80969a6-d128-48c1-890f-b43995806fbe",
        sourceEventOrdering={
            "accepted": True,
            "reason": "accepted",
            "recoveryEligible": False,
            "sourceTime": "2026-10-18T10:05:00+00:00",
            "eventId": "d80969a6-d128-48c1-890f-b43995806fbe",
        },
    )


def workflow_manager(triggers):
    manager = object.__new__(manager_module.WorkflowManager)
    manager.logger = logging.getLogger(__name__)
    manager.cel_environment = manager_module.celpy.Environment()
    workflows = [
        SimpleNamespace(id=str(i), workflow_triggers=[trigger])
        for i, trigger in enumerate(triggers)
    ]
    manager.workflow_store = SimpleNamespace(
        get_all_workflows=lambda *a, **k: workflows
    )
    manager._get_workflow_from_store = lambda tenant, workflow: workflow
    manager.scheduler = SimpleNamespace(lock=threading.Lock(), workflows_to_run=[])
    return manager


@pytest.fixture(params=["sqlite", "postgresql"])
def isolated_history(monkeypatch, request):
    schema = None
    url = os.environ.get("KEEP_TEST_ORDERING_POSTGRES_URL")
    if request.param == "postgresql":
        if not url:
            pytest.skip(
                "Set KEEP_TEST_ORDERING_POSTGRES_URL to a disposable PostgreSQL database"
            )
        schema = "workflow_ordering_" + uuid.uuid4().hex
        with create_engine(url).begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[Tenant.__table__, Alert.__table__, LastAlert.__table__]
    )
    with Session(engine) as session:
        session.add(Tenant(id="tenant", name="isolated regression"))
        session.commit()
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(manager_module, "get_enrichment", lambda *a, **k: None)
    yield engine
    engine.dispose()
    if schema:
        cleanup = create_engine(url)
        with cleanup.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        cleanup.dispose()


def save_transition(
    session, *, status, source_minute, ingest_minute, accepted, severity="info"
):
    event = alert_event()
    event.status, event.severity = status, severity
    event.lastReceived = f"2026-10-18T10:{source_minute:02d}:00Z"
    event.sourceEventOrdering.update(
        accepted=accepted, sourceTime=f"2026-10-18T10:{source_minute:02d}:00+00:00"
    )
    row = Alert(
        tenant_id="tenant",
        fingerprint=event.fingerprint,
        provider_id="provider",
        provider_type="cloudwatch",
        event=event.dict(),
        timestamp=datetime(
            2026, 10, 18, 11, ingest_minute, tzinfo=timezone.utc
        ).replace(tzinfo=None),
    )
    session.add(row)
    session.flush()
    event.event_id = str(row.id)
    event.sourceEventOrdering["eventId"] = str(row.id)
    row.event = event.dict()
    session.commit()
    return event


@pytest.mark.parametrize(
    "trigger,previous,rejected,current",
    [
        (
            {"only_on_change": ["status"]},
            ("firing", "critical"),
            ("resolved", "info"),
            ("resolved", "info"),
        ),
        (
            {"severity_changed": True},
            ("firing", "warning"),
            ("firing", "critical"),
            ("firing", "critical"),
        ),
    ],
)
def test_rejected_history_does_not_suppress_accepted_change(
    isolated_history, trigger, previous, rejected, current
):
    with Session(isolated_history) as session:
        save_transition(
            session,
            status=previous[0],
            severity=previous[1],
            source_minute=1,
            ingest_minute=1,
            accepted=True,
        )
        save_transition(
            session,
            status=rejected[0],
            severity=rejected[1],
            source_minute=0,
            ingest_minute=2,
            accepted=False,
        )
        incoming = save_transition(
            session,
            status=current[0],
            severity=current[1],
            source_minute=5,
            ingest_minute=3,
            accepted=True,
        )
    manager = workflow_manager([{"type": "alert", **trigger}])
    manager.insert_events("tenant", [incoming])
    assert len(manager.scheduler.workflows_to_run) == 1
    with Session(isolated_history) as session:
        assert (
            len(session.exec(select(Alert)).all()) == 3
        )  # Rejected history remains inspectable.


def test_previous_accepted_event_uses_source_time_not_worker_clock(isolated_history):
    with Session(isolated_history) as session:
        save_transition(
            session, status="resolved", source_minute=0, ingest_minute=0, accepted=True
        )
        save_transition(
            session, status="firing", source_minute=1, ingest_minute=5, accepted=True
        )
        incoming = save_transition(
            session, status="resolved", source_minute=5, ingest_minute=1, accepted=True
        )
    manager = workflow_manager([{"type": "alert", "only_on_change": ["status"]}])
    manager.insert_events("tenant", [incoming])
    assert len(manager.scheduler.workflows_to_run) == 1


def test_previous_accepted_event_is_relative_to_the_triggering_event(isolated_history):
    with Session(isolated_history) as session:
        opening = save_transition(
            session, status="firing", source_minute=1, ingest_minute=1, accepted=True
        )
        recovery = save_transition(
            session, status="resolved", source_minute=5, ingest_minute=2, accepted=True
        )
        save_transition(
            session, status="firing", source_minute=6, ingest_minute=3, accepted=True
        )
    previous = db.get_previous_alert_by_fingerprint(
        "tenant", recovery.fingerprint, source_event_id=recovery.event_id
    )
    assert str(previous.id) == opening.event_id
    manager = workflow_manager([{"type": "alert", "only_on_change": ["status"]}])
    manager.insert_events("tenant", [recovery])
    assert len(manager.scheduler.workflows_to_run) == 1


def test_legacy_history_lookup_keeps_its_existing_behavior(isolated_history):
    with Session(isolated_history) as session:
        save_transition(
            session, status="firing", source_minute=1, ingest_minute=1, accepted=True
        )
        rejected = save_transition(
            session, status="resolved", source_minute=0, ingest_minute=2, accepted=False
        )
        save_transition(
            session, status="resolved", source_minute=5, ingest_minute=3, accepted=True
        )
    previous = db.get_previous_alert_by_fingerprint("tenant", "admitted-alarm")
    assert str(previous.id) == rejected.event_id


def test_source_comparison_refuses_cross_tenant_event_id(isolated_history):
    with Session(isolated_history) as session:
        incoming = save_transition(
            session, status="firing", source_minute=1, ingest_minute=1, accepted=True
        )
    with pytest.raises(ValueError, match="not found"):
        db.get_previous_alert_by_fingerprint(
            "other-tenant", incoming.fingerprint, source_event_id=incoming.event_id
        )


def test_manager_keeps_reserved_context_across_multiple_workflows(monkeypatch):
    incoming = alert_event()
    before = copy.deepcopy(incoming.sourceEventOrdering)
    overlay = {
        "fingerprint": "foreign-alarm",
        "sourceEventOrdering": {
            "accepted": True,
            "recoveryEligible": True,
            "eventId": "foreign-event",
        },
        "event_id": "foreign-event",
        "ticket_url": "https://example.invalid/ticket",
    }
    monkeypatch.setattr(
        manager_module,
        "get_enrichment",
        lambda *a, **k: SimpleNamespace(enrichments=overlay),
    )
    manager = workflow_manager(
        [
            {"type": "alert", "cel": "true"},
            {"type": "alert", "cel": "sourceEventOrdering.recoveryEligible == true"},
        ]
    )
    manager.insert_events("tenant", [incoming])
    assert len(manager.scheduler.workflows_to_run) == 1
    queued = manager.scheduler.workflows_to_run[0]["event"]
    assert queued.fingerprint == "admitted-alarm"
    assert queued.sourceEventOrdering == before
    assert queued.event_id == before["eventId"]
    assert queued.ticket_url == overlay["ticket_url"]


@pytest.mark.parametrize("ordered", [True, False])
def test_scheduler_retry_preserves_only_source_ordered_identity(monkeypatch, ordered):
    incoming = alert_event()
    if not ordered:
        del incoming.sourceEventOrdering
    before = copy.deepcopy(getattr(incoming, "sourceEventOrdering", None))
    overlay = {
        "fingerprint": "overlay-alarm",
        "sourceEventOrdering": {
            "accepted": True,
            "recoveryEligible": True,
            "eventId": "overlay-event",
        },
        "event_id": "overlay-event",
        "ticket_url": "https://example.invalid/ticket",
    }
    scheduler = object.__new__(scheduler_module.WorkflowScheduler)
    scheduler.logger = logging.getLogger(__name__)
    scheduler.lock = threading.Lock()
    scheduler.workflows_to_run = [
        {
            "workflow": SimpleNamespace(),
            "workflow_id": "workflow",
            "workflow_execution_id": "execution",
            "tenant_id": "tenant",
            "event": incoming,
            "triggered_by": "alert",
            "retry": True,
        }
    ]
    scheduler.futures = set()
    scheduler.executor = SimpleNamespace(
        submit=Mock(
            return_value=SimpleNamespace(add_done_callback=lambda callback: None)
        )
    )
    # An inert Future is hashable and never runs any provider.
    scheduler.executor.submit.return_value = Mock()
    monkeypatch.setattr(
        scheduler_module,
        "get_enrichment",
        lambda *a, **k: SimpleNamespace(enrichments=overlay),
    )
    scheduler._handle_event_workflows()
    scheduler.executor.submit.assert_called_once()
    executed = scheduler.executor.submit.call_args.args[5]
    assert executed.ticket_url == overlay["ticket_url"]
    if ordered:
        assert executed.fingerprint == "admitted-alarm"
        assert executed.sourceEventOrdering == before
        assert executed.event_id == before["eventId"]
    else:
        assert executed.fingerprint == overlay["fingerprint"]
        assert executed.sourceEventOrdering == overlay["sourceEventOrdering"]


def test_manager_keeps_legacy_overlay_behavior(monkeypatch):
    incoming = alert_event()
    del incoming.sourceEventOrdering
    monkeypatch.setattr(
        manager_module,
        "get_enrichment",
        lambda *a, **k: SimpleNamespace(
            enrichments={"fingerprint": "legacy-overlay", "service": "legacy-service"}
        ),
    )
    manager = workflow_manager([{"type": "alert"}])
    manager.insert_events("tenant", [incoming])
    queued = manager.scheduler.workflows_to_run[0]["event"]
    assert queued.fingerprint == "legacy-overlay"
    assert queued.service == "legacy-service"
