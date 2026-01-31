import datetime
import json
import logging
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

import celpy
from sqlmodel import Session, select

from keep.api.consts import KEEP_CORRELATION_ENABLED, MAINTENANCE_WINDOW_ALERT_STRATEGY
from opentelemetry import trace
from keep.api.core.db import (
    add_audit,
    get_alert_by_event_id,
    get_alerts_by_status,
    get_all_presets_dtos,
    get_last_alert_by_fingerprint,
    get_maintenance_windows_started,
    get_session_sync,
    recover_prev_alert_status,
    set_maintenance_windows_trace,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, AlertAudit
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.tasks.notification_cache import get_notification_cache
from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

tracer = trace.get_tracer(__name__)


def _now_utc() -> datetime.datetime:
    # Always aware UTC
    return datetime.datetime.now(datetime.UTC)


def _ensure_aware_utc(dt: datetime.datetime) -> datetime.datetime:
    # If DB gave naive timestamps, assume UTC (best we can do without schema guarantees)
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(datetime.UTC)


def _source_as_string(source: Any) -> Optional[str]:
    if isinstance(source, list):
        return str(source[0]) if source else None
    if source is None:
        return None
    return str(source)


def _source_as_list(source: Any) -> List[str]:
    if isinstance(source, list):
        return [str(x) for x in source if x is not None]
    if source is None:
        return []
    return [str(source)]


def _safe_serializable(obj: Any) -> Any:
    """
    Celpy conversion is picky. This ensures we don't blow up on UUID/datetime/etc.
    Keep it conservative.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (UUID,)):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _safe_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_safe_serializable(v) for v in obj]
    # Last resort
    return str(obj)


@contextmanager
def _session_scope(session: Session | None, logger: logging.Logger, ctx: str):
    """
    Own session if not provided:
      - commit on success
      - rollback on failure
      - close if owned
    If session is provided:
      - DO NOT commit automatically (caller owns the transaction boundary)
      - rollback on failure to keep session usable
    """
    owns = session is None
    s = session if session is not None else get_session_sync()
    try:
        yield s, owns
        if owns:
            s.commit()
    except Exception:
        logger.exception("DB operation failed: %s", ctx)
        try:
            s.rollback()
        except Exception:
            logger.exception("Rollback failed: %s", ctx)
        raise
    finally:
        if owns:
            try:
                s.close()
            except Exception:
                logger.exception("Session close failed: %s", ctx)


class MaintenanceWindowsBl:
    """
    Notes (because humans love surprises):
    - check_if_alert_in_maintenance_windows MAY mutate alert.status (by design, but now guarded).
    - We avoid overwriting previous_status if it's already set.
    - We never commit the whole session for audit writes; we flush and keep going.
    - Time comparisons are done with aware UTC to avoid "naive vs aware" explosions.
    """

    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self._owns_session = session is None
        self.session = session if session is not None else get_session_sync()

        # Load only rules that are active "right now" in UTC.
        # If DB stores naive, comparisons are still consistent because we use aware UTC
        # and later normalize rule timestamps defensively.
        now = _now_utc()

        stmt = (
            select(MaintenanceWindowRule)
            .where(MaintenanceWindowRule.tenant_id == tenant_id)
            .where(MaintenanceWindowRule.enabled.is_(True))  # correct boolean filtering
            .where(MaintenanceWindowRule.end_time >= now)
            .where(MaintenanceWindowRule.start_time <= now)
        )
        try:
            self.maintenance_rules = list(self.session.exec(stmt).all())
        except Exception:
            self.logger.exception("Failed to load maintenance window rules", extra={"tenant_id": tenant_id})
            self.maintenance_rules = []

    def close(self) -> None:
        # Prefer explicit close to __del__ roulette.
        if self._owns_session and self.session:
            try:
                self.session.close()
            except Exception:
                self.logger.exception("Failed closing owned session", extra={"tenant_id": self.tenant_id})

    def __del__(self):
        # Best-effort. Explicit close() is still better.
        try:
            self.close()
        except Exception:
            pass

    def check_if_alert_in_maintenance_windows(self, alert: AlertDto) -> bool:
        extra = {"tenant_id": self.tenant_id, "fingerprint": getattr(alert, "fingerprint", None)}

        if not self.maintenance_rules:
            self.logger.debug("No maintenance window rules for this tenant", extra={"tenant_id": self.tenant_id})
            return False

        self.logger.info("Checking maintenance window for alert", extra=extra)
        env = celpy.Environment()

        for rule in self.maintenance_rules:
            ignore_statuses = rule.ignore_statuses or []
            if alert.status in ignore_statuses:
                self.logger.debug(
                    "Alert status is configured to be ignored for this maintenance window",
                    extra={**extra, "maintenance_rule_id": getattr(rule, "id", None)},
                )
                continue

            # Defensive normalize
            r_start = _ensure_aware_utc(rule.start_time)
            r_end = _ensure_aware_utc(rule.end_time)

            # If query was correct, this should never trigger, but DB timezone weirdness happens.
            if r_end and r_end <= _now_utc():
                self.logger.debug(
                    "Skipping ended maintenance window rule",
                    extra={**extra, "maintenance_rule_id": getattr(rule, "id", None)},
                )
                continue

            if self.evaluate_cel(rule, alert, env, self.logger, extra):
                self.logger.info(
                    "Alert matches maintenance window",
                    extra={**extra, "maintenance_rule_id": getattr(rule, "id", None)},
                )

                # Audit is best-effort, never commit the whole world.
                try:
                    audit = AlertAudit(
                        tenant_id=self.tenant_id,
                        fingerprint=alert.fingerprint,
                        user_id="Keep",
                        action=ActionType.MAINTENANCE.value,
                        description=(
                            f"Alert in maintenance due to rule `{rule.name}`"
                            if not rule.suppress
                            else f"Alert suppressed due to maintenance rule `{rule.name}`"
                        ),
                    )
                    self.session.add(audit)
                    self.session.flush()  # flush, don't commit the entire session
                except Exception:
                    self.logger.exception(
                        "Failed to write audit for alert maintenance window",
                        extra={"tenant_id": self.tenant_id, "fingerprint": alert.fingerprint},
                    )
                    try:
                        self.session.rollback()  # keep session usable
                    except Exception:
                        self.logger.exception("Failed to rollback after audit write failure", extra=extra)

                if rule.suppress:
                    # If suppressing, we allow it through but override status.
                    if MAINTENANCE_WINDOW_ALERT_STRATEGY == "recover_previous_status":
                        # Only store previous_status once.
                        prev = getattr(alert, "previous_status", None)
                        if prev is None:
                            try:
                                setattr(alert, "previous_status", alert.status)
                            except Exception:
                                # If AlertDto forbids extra fields, we just don't store it.
                                self.logger.debug("AlertDto does not support previous_status field", extra=extra)
                        alert.status = AlertStatus.MAINTENANCE.value
                    else:
                        alert.status = AlertStatus.SUPPRESSED.value
                    return False

                return True

        self.logger.info("Alert does not match any maintenance window", extra=extra)
        return False

    @staticmethod
    def evaluate_cel(
        maintenance_window: MaintenanceWindowRule,
        alert: AlertDto | Alert,
        environment: celpy.Environment,
        logger: logging.Logger,
        logger_extra_info: dict,
    ) -> bool:
        cel_expr = preprocess_cel_expression(maintenance_window.cel_query)
        ast = environment.compile(cel_expr)
        prgm = environment.program(ast)

        # Build payload without mutating original structures
        if isinstance(alert, AlertDto):
            payload = alert.dict()
        else:
            if not alert.event or not isinstance(alert.event, dict):
                logger.debug(
                    "Alert has invalid event structure for CEL evaluation",
                    extra={**logger_extra_info, "maintenance_rule_id": maintenance_window.id},
                )
                return False
            payload = dict(alert.event)

        # Normalize source once, no mutation ping-pong
        payload["source"] = _source_as_string(payload.get("source"))

        # Convert safely
        activation = celpy.json_to_cel(_safe_serializable(payload))

        try:
            cel_result = prgm.evaluate(activation)

            # CRITICAL FIX: be strict about boolean
            if not isinstance(cel_result, bool):
                logger.warning(
                    "CEL returned non-boolean; treating as False",
                    extra={
                        **logger_extra_info,
                        "maintenance_rule_id": maintenance_window.id,
                        "cel_return_type": str(type(cel_result)),
                    },
                )
                return False

            return cel_result

        except celpy.evaluation.CELEvalError as e:
            error_msg = str(e).lower()
            if "no such member" in error_msg or "undeclared reference" in error_msg:
                logger.debug(
                    "Skipping maintenance window rule due to missing field",
                    extra={**logger_extra_info, "maintenance_rule_id": maintenance_window.id, "error": str(e)},
                )
                return False

            logger.error(
                "Unexpected CEL evaluation error",
                extra={**logger_extra_info, "maintenance_rule_id": maintenance_window.id, "error": str(e)},
            )
            return False

    @staticmethod
    def recover_strategy(logger: logging.Logger, session: Session | None = None) -> None:
        """
        Recover previous status for alerts marked as MAINTENANCE when windows are no longer active.
        Fixes:
        - correct session ownership + close
        - consistent timezone usage (aware UTC)
        - null checks on alert.event + source normalization
        - tenant window grouping (performance)
        - pusher None checks
        - reuse RulesEngine
        """
        logger.info("Starting recover strategy for maintenance windows review.")
        env = celpy.Environment()
        now = _now_utc()

        with _session_scope(session, logger, "recover_strategy") as (s, owns_session):
            windows: List[MaintenanceWindowRule] = get_maintenance_windows_started(s) or []
            alerts_in_maint: List[Alert] = get_alerts_by_status(AlertStatus.MAINTENANCE, s) or []

            # Group windows by tenant for O(n+m) behavior
            windows_by_tenant: dict[str, list[MaintenanceWindowRule]] = defaultdict(list)
            for w in windows:
                windows_by_tenant[w.tenant_id].append(w)

            fingerprints_to_check: set[Tuple[str, str]] = set()

            for alert in alerts_in_maint:
                active = False
                tenant_windows = windows_by_tenant.get(alert.tenant_id, [])

                # Validate alert.event structure before touching it
                if not alert.event or not isinstance(alert.event, dict):
                    logger.error(
                        "Alert has invalid event structure; skipping",
                        extra={"tenant_id": alert.tenant_id, "alert_id": alert.id, "fingerprint": alert.fingerprint},
                    )
                    continue

                for window in tenant_windows:
                    # Window active check with consistent timezone handling
                    w_start = _ensure_aware_utc(window.start_time)
                    w_end = _ensure_aware_utc(window.end_time)
                    is_enabled = bool(window.enabled)

                    if not (is_enabled and w_start and w_end):
                        continue

                    # Ensure alert.timestamp is comparable (assume UTC if naive)
                    a_ts = _ensure_aware_utc(alert.timestamp)

                    if a_ts and (w_start < a_ts < w_end) and (w_end > now):
                        logger.info(
                            "Checking alert in maintenance window",
                            extra={"tenant_id": alert.tenant_id, "alert_id": alert.id, "window_id": window.id},
                        )

                        is_in_cel = MaintenanceWindowsBl.evaluate_cel(
                            window,
                            alert,
                            env,
                            logger,
                            {"tenant_id": alert.tenant_id, "alert_id": alert.id},
                        )

                        # Keep event.source as list for downstream DTO creation (without risky assumptions)
                        alert.event["source"] = _source_as_list(alert.event.get("source"))

                        if is_in_cel:
                            active = True
                            set_maintenance_windows_trace(alert, window, s)
                            logger.info(
                                "Alert remains blocked by maintenance window",
                                extra={"tenant_id": alert.tenant_id, "alert_id": alert.id, "window_id": window.id},
                            )
                            break

                if not active:
                    # Recover previous status (DB write expected)
                    recover_prev_alert_status(alert, s)
                    fingerprints_to_check.add((alert.tenant_id, alert.fingerprint))

                    # Audit is best-effort: write through DB helper (may or may not commit internally)
                    try:
                        add_audit(
                            tenant_id=alert.tenant_id,
                            fingerprint=alert.fingerprint,
                            user_id="system",
                            action=ActionType.MAINTENANCE_EXPIRED,
                            description=(
                                f"Alert {alert.id} recovered previous status, "
                                f"from {alert.event.get('previous_status')} to {alert.event.get('status')}"
                            ),
                            session=s,
                            commit=False,
                        )
                        s.flush()
                    except Exception:
                        logger.exception(
                            "Failed to add audit for recovered alert",
                            extra={"tenant_id": alert.tenant_id, "fingerprint": alert.fingerprint, "alert_id": alert.id},
                        )
                        try:
                            s.rollback()
                        except Exception:
                            logger.exception("Rollback failed after audit failure")

            # If we own the session, commits happen via _session_scope at the end.
            # If not, caller controls commit.

            # Push recovered alerts through workflows/rules/pushers like a “new alert” would.
            pusher_cache = get_notification_cache()
            pusher_client = get_pusher_client()

            for (tenant, fp) in fingerprints_to_check:
                last_alert = get_last_alert_by_fingerprint(tenant, fp, s)
                if not last_alert:
                    continue

                alert = get_alert_by_event_id(tenant, str(last_alert.alert_id), s)
                if not alert or not alert.event or not isinstance(alert.event, dict):
                    logger.error(
                        "Recovered alert has invalid event structure; skipping",
                        extra={"tenant_id": tenant, "fingerprint": fp},
                    )
                    continue

                if "previous_status" not in alert.event:
                    logger.info(
                        "Alert does not have previous_status; cannot proceed",
                        extra={
                            "tenant_id": tenant,
                            "fingerprint": fp,
                            "alert_id": getattr(alert, "id", None),
                            "alert.status": alert.event.get("status"),
                        },
                    )
                    continue

                # Normalize source for AlertDto construction
                alert.event["source"] = _source_as_list(alert.event.get("source"))

                try:
                    alert_dto = AlertDto(**alert.event)
                except Exception:
                    logger.exception(
                        "Failed to construct AlertDto from alert.event",
                        extra={"tenant_id": tenant, "fingerprint": fp, "alert_id": getattr(alert, "id", None)},
                    )
                    continue

                with tracer.start_as_current_span("mw_recover_strategy_push_to_workflows"):
                    try:
                        workflow_manager = WorkflowManager.get_instance()
                        logger.info("Queueing event to workflow manager", extra={"tenant_id": tenant})
                        workflow_manager.insert_events(tenant, [alert_dto])
                    except Exception:
                        logger.exception(
                            "Failed to run workflows based on alerts",
                            extra={
                                "provider_type": getattr(alert_dto, "providerType", None),
                                "provider_id": getattr(alert_dto, "providerId", None),
                                "tenant_id": tenant,
                            },
                        )

                # Reuse one RulesEngine instance per tenant per pass (not twice like before)
                rules_engine = RulesEngine(tenant_id=tenant)

                with tracer.start_as_current_span("mw_recover_strategy_run_rules_engine"):
                    if KEEP_CORRELATION_ENABLED:
                        incidents = []
                        try:
                            incidents = rules_engine.run_rules([alert_dto], session=s)
                        except Exception:
                            logger.exception(
                                "Failed to run rules engine",
                                extra={
                                    "provider_type": getattr(alert_dto, "providerType", None),
                                    "provider_id": getattr(alert_dto, "providerId", None),
                                    "tenant_id": tenant,
                                },
                            )

                        if incidents and pusher_cache.should_notify(tenant, "incident-change"):
                            if pusher_client:
                                try:
                                    pusher_client.trigger(f"private-{tenant}", "incident-change", {})
                                except Exception:
                                    logger.exception("Failed to tell the client to pull incidents", extra={"tenant_id": tenant})

                    # Presets push (reuse same rules_engine)
                    try:
                        presets = get_all_presets_dtos(tenant) or []
                        presets_do_update = []
                        for preset_dto in presets:
                            filtered_alerts = rules_engine.filter_alerts([alert_dto], preset_dto.cel_query)
                            if filtered_alerts:
                                presets_do_update.append(preset_dto)

                        if presets_do_update and pusher_cache.should_notify(tenant, "poll-presets"):
                            if pusher_client:
                                try:
                                    pusher_client.trigger(
                                        f"private-{tenant}",
                                        "poll-presets",
                                        json.dumps([p.name.lower() for p in presets_do_update], default=str),
                                    )
                                except Exception:
                                    logger.exception("Failed to send presets via pusher", extra={"tenant_id": tenant})
                    except Exception:
                        logger.exception(
                            "Failed to evaluate/send presets via pusher",
                            extra={
                                "provider_type": getattr(alert_dto, "providerType", None),
                                "provider_id": getattr(alert_dto, "providerId", None),
                                "tenant_id": tenant,
                            },
                        )

        logger.info("Finished recover strategy for maintenance windows review.")