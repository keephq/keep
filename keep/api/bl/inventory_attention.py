"""Inventory attention on Keep 0.55 native tables. Never mutates Odoo jobs.

Incident and AlertEnrichment are Keep's existing tables. Private policy state is
serialized in the database; the native interval workflow is only a clock driver.
A claimed remote effect without a receipt becomes UNKNOWN, never a blind retry.
"""
from __future__ import annotations

import hashlib
import copy
import json
import math
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4, uuid5

from sqlalchemy import insert, select, update, MetaData, UniqueConstraint
from keep.api.models.db.alert import AlertAudit, AlertEnrichment
from keep.api.models.db.incident import Incident
from keep.api.models.db.rule import ResolveOn, Rule
from keep.api.models.db.tenant import Tenant

CHANNEL = "root.inventory_orchestrator"
NAMESPACE = UUID("e27f2362-799c-4e83-a984-f6d0f656790a")
PREFIX = "inventory-policy:"
OWNER = "inventory-attention-v1:"


class KnownNotDelivered(Exception):
    """Adapter positively knows no remote effect occurred; bounded retry allowed."""


@dataclass(frozen=True)
class Policy:
    policy_id: str
    enabled: bool
    shared_channel: str
    primary: str
    backup: str
    incident_lead: str
    primary_after_seconds: int
    ack_seconds: int
    claim_timeout_seconds: int
    max_notification_attempts: int
    allowed_humans: tuple[str, ...]
    coverage: str
    closure_policy: str
    reconciliation_seconds: int | None = None

    def validate(self) -> None:
        if not self.enabled:
            return
        for value in (self.policy_id, self.shared_channel, self.primary, self.backup,
                      self.incident_lead, self.coverage, self.closure_policy):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("An enabled policy requires every operational decision")
        if self.reconciliation_seconds is not None and (type(self.reconciliation_seconds) is not int or not 0 < self.reconciliation_seconds <= 604800):
            raise ValueError("Reconciliation deadline must be explicitly positive and bounded")
        if not self.allowed_humans:
            raise ValueError("An enabled policy requires approved human actors")
        for value in (self.primary_after_seconds, self.ack_seconds,
                      self.claim_timeout_seconds, self.max_notification_attempts):
            if type(value) is not int or not 0 < value <= 604800:
                raise ValueError("Policy limits must be explicitly positive and bounded")
        if self.max_notification_attempts > 10:
            raise ValueError("Notification attempts must be at most ten")


def create_test_schema(engine) -> None:
    """Tests only, native tables with the installed migration's unique constraint.

    Upstream ORM metadata is stale: migrations 16309df224d1/2a6132b443ab
    replace fingerprint-only uniqueness with tenant+fingerprint. Do not mutate
    production model metadata or add a new application migration to mask this.
    """
    Tenant.__table__.create(engine, checkfirst=True)
    Rule.__table__.create(engine, checkfirst=True)
    Incident.__table__.create(engine, checkfirst=True)
    fixture_metadata = MetaData()
    Tenant.__table__.to_metadata(fixture_metadata)
    enrichment = AlertEnrichment.__table__.to_metadata(fixture_metadata)
    for constraint in list(enrichment.constraints):
        if isinstance(constraint, UniqueConstraint):
            enrichment.constraints.remove(constraint)
    enrichment.append_constraint(UniqueConstraint("tenant_id", "alert_fingerprint",
                                                  name="uc_alertenrichment_tenant_fingerprint"))
    enrichment.create(engine, checkfirst=True)
    AlertAudit.__table__.create(engine, checkfirst=True)


def _bounded(value: object, limit: int = 256) -> str:
    return " ".join(str(value).split())[:limit]


class InventoryAttentionService:
    def __init__(self, engine, tenant_id: str, policy: Policy,
                 clock: Callable[[], float] = time.time):
        policy.validate()
        self.engine, self.tenant_id, self.policy, self.clock = engine, tenant_id, policy, clock
        self.policy_digest = hashlib.sha256(json.dumps(asdict(policy), sort_keys=True).encode()).hexdigest()

    @contextmanager
    def _transaction(self):
        with self.engine.connect() as connection:
            try:
                if connection.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                elif connection.dialect.name == "postgresql":
                    connection.begin()
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '8s'")
                    connection.exec_driver_sql("SET LOCAL lock_timeout = '3s'")
                else:
                    raise ValueError("Only PostgreSQL and SQLite have verified lock semantics")
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _key(self, incident_id: str) -> str:
        return f"{PREFIX}{self.tenant_id}:{incident_id}"

    def _load(self, connection, incident_id: str) -> dict:
        query = select(AlertEnrichment.__table__).where(
            AlertEnrichment.tenant_id == self.tenant_id,
            AlertEnrichment.alert_fingerprint == self._key(incident_id),
        ).with_for_update()
        row = connection.execute(query).mappings().first()
        if row is None:
            raise LookupError("No owned Inventory incident")
        state = copy.deepcopy(row["enrichments"])
        if state.get("policy_digest") != self.policy_digest:
            raise ValueError("Policy changed under the same ID; explicit migration required")
        return state

    def _save(self, connection, state: dict) -> None:
        state["revision"] += 1
        connection.execute(update(AlertEnrichment.__table__).where(
            AlertEnrichment.tenant_id == self.tenant_id,
            AlertEnrichment.alert_fingerprint == self._key(state["incident_id"]),
        ).values(enrichments=state, timestamp=datetime.now(timezone.utc)))
        summary = {key: state.get(key) for key in (
            "kind", "correlation", "missing", "ack", "primary_due_at", "ack_due_at", "delivery_gap", "attention", "status", "resolution", "generation"
        )}
        summary["notifications"] = {
            key: {field: notice.get(field) for field in ("status", "attempts", "reason")}
            for key, notice in state["notifications"].items()
        }
        connection.execute(update(Incident.__table__).where(
            Incident.id == UUID(state["incident_id"]), Incident.tenant_id == self.tenant_id,
        ).values(user_summary=json.dumps(summary)))

    def snapshot(self, incident_id: str) -> dict:
        with self._transaction() as connection:
            return self._load(connection, incident_id)

    def _seed(self, connection, incident_id: str, now: float) -> dict:
        # Dialect upsert uses the native UNIQUE fingerprint as first-writer fence.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        dialect_insert = sqlite_insert if connection.dialect.name == "sqlite" else pg_insert
        existing_incident = connection.execute(select(Incident.id).where(Incident.id == UUID(incident_id))).first()
        existing_state = connection.execute(select(AlertEnrichment.id).where(
            AlertEnrichment.tenant_id == self.tenant_id,
            AlertEnrichment.alert_fingerprint == self._key(incident_id))).first()
        if existing_incident and not existing_state:
            raise ValueError("Owned incident lost durable policy state; quarantine requires manual reconciliation")
        state = dict(incident_id=incident_id, policy_id=self.policy.policy_id,
                     policy_digest=self.policy_digest, applied_policy=asdict(self.policy),
                     revision=0, generation=1, history=[], created_at=now, last_observed_at=-1.0,
                     primary_due_at=now + self.policy.primary_after_seconds,
                     ack_due_at=None, ack=None, status="open", thread_ts=None,
                     correlation={}, evidence={}, missing=[], notifications={},
                     last_signal=None, recovery_signal_seen=False)
        connection.execute(dialect_insert(AlertEnrichment.__table__).values(
            id=uuid4(), tenant_id=self.tenant_id, timestamp=datetime.now(timezone.utc),
            alert_fingerprint=self._key(incident_id), enrichments=state,
        ).on_conflict_do_nothing(index_elements=["tenant_id", "alert_fingerprint"]))
        state = self._load(connection, incident_id)
        existing = connection.execute(select(Incident.__table__).where(
            Incident.id == UUID(incident_id))).mappings().first()
        if existing and existing["tenant_id"] != self.tenant_id:
            raise ValueError("Incident identity belongs to another tenant")
        if not existing:
            connection.execute(insert(Incident.__table__).values(
                id=UUID(incident_id), tenant_id=self.tenant_id,
                user_generated_name="Inventory attention", user_summary="Evidence pending",
                generated_summary="", status="firing", assignee=None,
                fingerprint=f"{OWNER}{incident_id}", resolve_on=ResolveOn.NEVER.value,
                sources=["grafana"], affected_services=["inventory"],
            ))
        return state

    def ingest(self, signal: dict) -> dict:
        if not self.policy.enabled:
            return {"status": "disabled"}
        if signal.get("channel") != CHANNEL:
            raise ValueError("Signal does not belong to Inventory")
        kind = signal.get("kind")
        if kind not in {"parent_failed", "parent_unknown", "coverage_unknown", "no_progress", "recovery"}:
            raise ValueError("Unsupported signal kind")
        now, observed = float(self.clock()), float(signal["observed_at"])
        if not math.isfinite(observed) or not math.isfinite(now) or observed > now + 300 or observed < 0:
            raise ValueError("Untrusted observation time")
        job = signal.get("job_uuid")
        source_key = job if job is not None and job != "" else signal.get("source_fingerprint")
        if not isinstance(source_key, str) or not source_key.strip() or len(source_key) > 128:
            raise ValueError("Stable identity must be a nonempty string of at most 128 characters")
        job = job or ""
        if not source_key:
            raise ValueError("A stable job or source fingerprint is required")
        incident_id = str(uuid5(NAMESPACE, f"{self.tenant_id}|{self.policy.policy_id}|{CHANNEL}|{source_key}"))
        with self._transaction() as connection:
            state = self._seed(connection, incident_id, now)
            if state["status"] == "closed":
                # Receipt freshness never proves a new business occurrence.
                return state
            if observed <= state["last_observed_at"]:
                return state
            state["last_observed_at"] = observed
            state["last_signal"] = _bounded(signal.get("event_id", "missing"))
            state["recovery_signal_seen"] |= kind == "recovery"
            for key in ("job_uuid", "graph_uuid", "operation_id"):
                value = signal.get(key)
                if value is not None and value != "":
                    previous = state["correlation"].get(key)
                    if previous and previous != _bounded(value):
                        state["missing"] = sorted(set(state["missing"] + [f"conflicting_{key}"]))
                    else:
                        state["correlation"][key] = _bounded(value)
            evidence = signal.get("evidence", {})
            # Only aggregate/status metadata. Raw exceptions, payloads and logs are excluded.
            allowed = {"source", "captured_at", "queue_state", "business_state", "completeness", "truncated"}
            state["evidence"] = {k: _bounded(v, 512) for k, v in evidence.items() if k in allowed}
            missing = [k for k in ("job_uuid", "graph_uuid", "operation_id") if k not in state["correlation"]]
            if not evidence:
                missing.append("evidence")
            missing.extend(f"evidence.{key}" for key in ("source", "captured_at", "queue_state", "completeness") if not evidence.get(key))
            if kind == "no_progress":
                # A timer cannot create accepted_at or a durable business receipt.
                missing.extend(["accepted_at", "last_verified_success_at"])
                kind = "coverage_unknown"
            state["kind"] = kind
            state["missing"] = sorted(set(state["missing"] + missing))
            # Recovery/queue done NEVER closes or resets clocks/ACK/deadlines.
            connection.execute(update(Incident.__table__).where(
                Incident.id == UUID(incident_id), Incident.tenant_id == self.tenant_id,
            ).values(last_seen_time=datetime.fromtimestamp(now, timezone.utc),
                     user_summary=json.dumps({"correlation": state["correlation"], "missing": state["missing"]})))
            self._save(connection, state)
            return state

    def _authorize(self, actor):
        if not self.policy.enabled:
            raise PermissionError("Inventory policy is inactive")
        if (actor.tenant_id != self.tenant_id or actor.api_key_name is not None
                or actor.email not in self.policy.allowed_humans):
            raise PermissionError("Only a verified approved person can assume attention")

    def acknowledge(self, incident_id: str, actor) -> dict:
        self._authorize(actor)
        if (actor.tenant_id != self.tenant_id or actor.api_key_name is not None
                or actor.email not in self.policy.allowed_humans):
            raise PermissionError("Only a verified approved person can assume attention")
        with self._transaction() as connection:
            state = self._load(connection, incident_id)
            if state["status"] == "closed":
                raise ValueError("Closed incident requires explicit authorized reopen")
            if state["ack"]:
                return state
            state["ack"] = {"actor": actor.email, "at": self.clock()}
            connection.execute(update(Incident.__table__).where(
                Incident.id == UUID(incident_id), Incident.tenant_id == self.tenant_id,
            ).values(status="acknowledged", assignee=actor.email))
            connection.execute(insert(AlertAudit.__table__).values(
                id=uuid4(), tenant_id=self.tenant_id, fingerprint=incident_id,
                user_id=actor.email, action="Incident status changed",
                description="Inventory human ACK; ownership assumed, not resolved",
                timestamp=datetime.now(timezone.utc),
            ))
            self._save(connection, state)
            return state

    def _claim(self, incident_id: str) -> tuple[dict, str] | None:
        now = float(self.clock())
        with self._transaction() as connection:
            state = self._load(connection, incident_id)
            if state["status"] == "closed":
                self._save(connection, state)
                return None
            notices = state["notifications"]
            for notice in notices.values():
                if notice["status"] == "claimed" and now >= notice["claimed_at"] + self.policy.claim_timeout_seconds:
                    notice["status"] = "unknown"
                    notice["reason"] = "worker_lost_or_slow_no_receipt"
                    notice["uncertain_at"] = now
            self._attention(connection, state, now)
            transition = None
            if "initial" not in notices or notices["initial"]["status"] == "retryable":
                transition = "initial"
            elif not state["ack"] and now >= state["primary_due_at"]:
                if state["ack_due_at"] is not None and now >= state["ack_due_at"]:
                    if "backup" not in notices or notices["backup"]["status"] == "retryable":
                        transition = "backup"
                elif "primary" not in notices or notices["primary"]["status"] == "retryable":
                    transition = "primary"
            if transition and transition != "initial" and not state["thread_ts"]:
                # Never create a second root thread to escape an ambiguous initial send.
                state["delivery_gap"] = "root_receipt_missing"
                transition = None
            if not transition:
                self._save(connection, state)
                return None
            previous = notices.get(transition, {})
            attempts = previous.get("attempts", 0)
            if attempts >= self.policy.max_notification_attempts:
                notices[transition]["status"] = "exhausted"
                self._attention(connection, state, now)
                self._save(connection, state)
                return None
            notices[transition] = dict(status="claimed", attempts=attempts + 1,
                                       intended_responsible={"initial": self.policy.shared_channel, "primary": self.policy.primary, "backup": [self.policy.backup, self.policy.incident_lead]}[transition],
                                       claimed_at=now, claim_id=f"{incident_id}:{state.get('generation', 1)}:{transition}:{attempts + 1}")
            notices[transition]["transport_policy"] = state.get("transport_policy")
            if transition == "primary" and state["ack_due_at"] is None:
                state["ack_due_at"] = now + self.policy.ack_seconds
            self._save(connection, state)
            return state, transition

    def dispatch(self, incident_id: str, notifier) -> dict:
        if not self.policy.enabled:
            return {"status": "disabled"}
        if hasattr(notifier, "policy_binding"):
            binding = notifier.policy_binding()
            with self._transaction() as connection:
                state = self._load(connection, incident_id)
                if state.get("transport_policy") not in (None, binding):
                    raise ValueError("Transport policy changed; explicit migration required")
                state["transport_policy"] = binding
                self._save(connection, state)
        claimed = self._claim(incident_id)
        if claimed is None:
            return self._dispatch_fallback(incident_id, notifier)
        state, transition = claimed
        claim = state["notifications"][transition]
        recipient = {"initial": "shared-channel", "primary": self.policy.primary,
                     "backup": f"{self.policy.backup}; {self.policy.incident_lead}"}[transition]
        message = json.dumps({"incident_id": incident_id, "transition": transition,
                              "responsible": recipient, "kind": state.get("kind"),
                              "correlation": state["correlation"], "evidence": state["evidence"],
                              "missing": state["missing"], "recovery_authorized": False})
        try:
            receipt = notifier.send(transition=transition, text=message,
                                    thread_ts=state["thread_ts"], idempotency_key=claim["claim_id"])
            if not isinstance(receipt, str) or not receipt.strip():
                raise RuntimeError("No verifiable delivery receipt")
            outcome, reason = "sent", None
        except KnownNotDelivered:
            receipt, outcome, reason = None, "retryable", "known_not_delivered"
        except Exception:
            receipt, outcome, reason = None, "unknown", "ambiguous_notification_result"
        # Failure/commit uncertainty here leaves a durable claim; sweep marks unknown.
        with self._transaction() as connection:
            current = self._load(connection, incident_id)
            target = current
            if current.get("generation", 1) != state.get("generation", 1):
                target = next(h for h in current["history"] if h["generation"] == state.get("generation", 1))
            notice = target["notifications"][transition]
            if notice["claim_id"] != claim["claim_id"]:
                raise RuntimeError("Notification ownership changed")
            notice.update(status=outcome, reason=reason, receipt=receipt)
            if outcome == "unknown":
                notice["uncertain_at"] = float(self.clock())
            if outcome == "retryable" and notice["attempts"] >= self.policy.max_notification_attempts:
                notice["status"] = "exhausted"
            if target is current:
                self._attention(connection, current, float(self.clock()))
            if outcome == "sent":
                if transition == "initial":
                    target["thread_ts"] = receipt
            self._save(connection, current)
            return current

    def _audit(self, connection, state, actor, description):
        connection.execute(insert(AlertAudit.__table__).values(
            id=uuid4(), tenant_id=self.tenant_id, fingerprint=state["incident_id"],
            user_id=actor, action="Incident status changed", description=description,
            timestamp=datetime.now(timezone.utc)))

    def _attention(self, connection, state, now):
        problematic = [n for n in state["notifications"].values()
                       if n["status"] in ("unknown", "exhausted")]
        if not problematic:
            return
        deadline = min(n.get("uncertain_at", n["claimed_at"]) for n in problematic)
        deadline += self.policy.reconciliation_seconds or self.policy.claim_timeout_seconds
        attention = state.setdefault("attention", {
            "status": "reconciliation_required", "due_at": deadline,
            "responsible": self.policy.incident_lead, "fallback": None})
        if now >= attention["due_at"] or any(n["status"] == "exhausted" for n in problematic):
            attention["status"] = "manual_attention_required"
        connection.execute(update(Incident.__table__).where(
            Incident.id == UUID(state["incident_id"]), Incident.tenant_id == self.tenant_id,
        ).values(assignee=(state.get("ack") or {}).get("actor", self.policy.incident_lead)))

    def _dispatch_fallback(self, incident_id, notifier):
        now = float(self.clock())
        with self._transaction() as connection:
            state = self._load(connection, incident_id)
            attention = state.get("attention")
            if state["status"] == "closed" or not attention or attention["status"] != "manual_attention_required":
                return state
            fallback = attention.get("fallback")
            if fallback:
                if fallback["status"] == "claimed" and now >= fallback["at"] + self.policy.claim_timeout_seconds:
                    fallback.update(status="unknown", reason="fallback_worker_lost_no_receipt")
                    self._save(connection, state)
                return state
            attention["fallback"] = {"status": "claimed", "at": now,
                                     "claim_id": f"{incident_id}:{state.get('generation', 1)}:fallback"}
            self._audit(connection, state, "inventory-attention", "Notification evidence incomplete; assigned independent manual attention queue")
            self._save(connection, state)
        try:
            if not hasattr(notifier, "send_fallback"):
                raise KnownNotDelivered("No independent provider configured")
            receipt = notifier.send_fallback(incident_id=incident_id,
                text=json.dumps({"incident_id": incident_id, "attention": attention, "missing": state["missing"]}),
                idempotency_key=attention["fallback"]["claim_id"])
            if not isinstance(receipt, str) or not receipt.strip():
                raise RuntimeError("No independent delivery receipt")
            result = {"status": "confirmed", "receipt": receipt}
        except KnownNotDelivered:
            result = {"status": "failed", "reason": "independent_route_not_delivered"}
        except Exception:
            result = {"status": "unknown", "reason": "independent_delivery_uncertain"}
        with self._transaction() as connection:
            current = self._load(connection, incident_id)
            # Closure/reopen cannot erase an in-flight effect history.
            target = current
            if current.get("generation", 1) != state.get("generation", 1):
                target = next(h for h in current["history"] if h["generation"] == state.get("generation", 1))
            target["attention"]["fallback"].update(result)
            self._save(connection, current)
            return current

    def resolve(self, incident_id, actor, *, expected_revision, evidence):
        self._authorize(actor)
        if not isinstance(evidence, dict) or evidence.get("type") != "business_reconciliation":
            raise ValueError("Business reconciliation evidence is required")
        refs = evidence.get("references")
        def valid_refs(values):
            return (isinstance(values, list) and 1 <= len(values) <= 10
                    and all(isinstance(r, str) and (r.startswith("https://") or r.startswith("urn:"))
                            and len(r) <= 1024 for r in values))
        checked_at = evidence.get("checked_at")
        scope = evidence.get("operation_scope")
        if (not valid_refs(refs) or not isinstance(evidence.get("summary"), str)
                or not evidence["summary"].strip() or len(evidence["summary"]) > 2048
                or not isinstance(scope, list) or not 1 <= len(scope) <= 100
                or any(not isinstance(x, str) or not x.strip() or len(x) > 256 for x in scope)
                or not isinstance(checked_at, (int, float)) or isinstance(checked_at, bool)
                or not math.isfinite(checked_at) or not 0 <= checked_at <= self.clock()):
            raise ValueError("Bounded proof references, summary, operation scope and checked_at are required")
        reconciliation = evidence.get("notification_reconciliation")
        if reconciliation is not None and (not isinstance(reconciliation, dict)
                or reconciliation.get("outcome") not in ("delivered", "not_delivered")
                or not valid_refs(reconciliation.get("references"))
                or (reconciliation.get("outcome") == "delivered" and
                    (not isinstance(reconciliation.get("thread_ts"), str) or not reconciliation["thread_ts"].strip()))):
            raise ValueError("Separate bounded notification reconciliation proof required")
        with self._transaction() as connection:
            state = self._load(connection, incident_id)
            if state["revision"] != expected_revision:
                raise ValueError("Stale revision")
            if state["status"] == "closed" or not state["ack"] or state["ack"]["actor"] != actor.email:
                raise PermissionError("Resolution requires the approved person who assumed attention")
            fallback = (state.get("attention") or {}).get("fallback") or {}
            unresolved_claims = {n["claim_id"] for n in state["notifications"].values()
                                 if n["status"] in ("claimed", "unknown")}
            if fallback.get("status") in ("claimed", "unknown"):
                unresolved_claims.add(fallback["claim_id"])
            covered = (reconciliation or {}).get("claim_ids", [])
            if (not isinstance(covered, list) or any(not isinstance(c, str) for c in covered)
                    or not unresolved_claims.issubset(set(covered))):
                raise ValueError("Closure must separately reconcile every outstanding notification claim")
            operation_id = state["correlation"].get("operation_id")
            if operation_id and operation_id not in scope:
                raise ValueError("Business proof does not cover the correlated inventory operation")
            state["status"] = "closed"
            state["resolution"] = {"actor": actor.email, "at": self.clock(), "evidence": copy.deepcopy(evidence)}
            connection.execute(update(Incident.__table__).where(
                Incident.id == UUID(incident_id), Incident.tenant_id == self.tenant_id,
            ).values(status="resolved", end_time=datetime.fromtimestamp(self.clock(), timezone.utc)))
            self._audit(connection, state, actor.email, "Inventory business reconciliation: " + json.dumps(evidence))
            self._save(connection, state)
            return state

    def reopen(self, incident_id, actor, *, expected_revision, reason):
        self._authorize(actor)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2048:
            raise ValueError("Explicit bounded recurrence decision is required")
        with self._transaction() as connection:
            state = self._load(connection, incident_id)
            if state["revision"] != expected_revision or state["status"] != "closed":
                raise ValueError("Expected a closed incident at the supplied revision")
            # Unknown previous root delivery must be reconciled by the human closure;
            # preserve all historical claims, receipts and attention, including late receipts.
            uncertain = any(n["status"] in ("claimed", "unknown") for n in state["notifications"].values())
            reconciliation = (state.get("resolution") or {}).get("evidence", {}).get("notification_reconciliation", {})
            if uncertain and (not isinstance(reconciliation, dict) or reconciliation.get("outcome") not in ("delivered", "not_delivered")
                              or not reconciliation.get("references")
                              or (reconciliation.get("outcome") == "delivered" and not reconciliation.get("thread_ts"))):
                raise ValueError("Reopen requires explicit reconciliation of uncertain notification delivery")
            old_thread = state["thread_ts"] or reconciliation.get("thread_ts")
            initial = ({"initial": {"status": "sent", "attempts": 0, "receipt": old_thread,
                        "reason": "known_thread_reused_for_authorized_generation"}} if old_thread else {})
            history = state.setdefault("history", [])
            history.append({k: copy.deepcopy(v) for k, v in state.items() if k != "history"})
            state.update(generation=state.get("generation", 1) + 1, status="open", ack=None,
                         ack_due_at=None, primary_due_at=self.clock() + self.policy.primary_after_seconds,
                         notifications=initial, thread_ts=old_thread, resolution=None,
                         reopen={"actor": actor.email, "at": self.clock(), "reason": reason})
            state.pop("attention", None)
            state.pop("delivery_gap", None)
            connection.execute(update(Incident.__table__).where(
                Incident.id == UUID(incident_id), Incident.tenant_id == self.tenant_id,
            ).values(status="firing", end_time=None, assignee=None))
            self._audit(connection, state, actor.email, "Inventory explicit new occurrence: " + reason)
            self._save(connection, state)
            return state

    def sweep(self, notifier, limit: int = 100) -> list[dict]:
        if not self.policy.enabled:
            return []
        if not 1 <= limit <= 100:
            raise ValueError("Sweep must be bounded")
        with self.engine.connect() as connection:
            rows = connection.execute(select(AlertEnrichment.alert_fingerprint, AlertEnrichment.enrichments).where(
                AlertEnrichment.tenant_id == self.tenant_id,
                AlertEnrichment.enrichments["policy_id"].as_string() == self.policy.policy_id,
                AlertEnrichment.alert_fingerprint.startswith(f"{PREFIX}{self.tenant_id}:"),
            ).order_by(AlertEnrichment.timestamp).limit(limit)).mappings().all()
        results = []
        for record in rows:
            row = record["enrichments"]
            try:
                results.append(self.dispatch(row["incident_id"], notifier))
            except Exception as error:
                # Rotate a quarantined row without trusting its policy/schema. Other
                # incidents must continue; the native queue retains explicit coverage.
                incident_id = row.get("incident_id") if isinstance(row, dict) else None
                with self._transaction() as connection:
                    connection.execute(update(AlertEnrichment.__table__).where(
                        AlertEnrichment.tenant_id == self.tenant_id,
                        AlertEnrichment.alert_fingerprint == record["alert_fingerprint"],
                    ).values(timestamp=datetime.now(timezone.utc)))
                    try:
                        valid_id = UUID(str(incident_id))
                    except (ValueError, TypeError, AttributeError):
                        valid_id = None
                    if valid_id:
                        connection.execute(update(Incident.__table__).where(
                            Incident.id == valid_id, Incident.tenant_id == self.tenant_id,
                        ).values(user_summary=json.dumps({"attention": "manual_attention_required", "coverage_error": type(error).__name__}), assignee=self.policy.incident_lead))
                results.append({"incident_id": incident_id, "status": "quarantined", "coverage_error": type(error).__name__})
        return results
