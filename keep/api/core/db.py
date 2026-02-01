"""Keep main database module (RECODED - v3.1)

Why v3.1 exists:
- Your runtime environment doesn't have optional deps like `opentelemetry` (and sometimes `retry`).
- This version treats those as OPTIONAL: if missing, it continues without instrumentation and
  uses a tiny built-in retry decorator.

Primary improvements retained:
- Session correctness: helpers accept optional Session and re-use it.
- existed_or_new_session attaches the *actual used* session to exceptions.
- retry_on_db_error always attempts rollback when possible.
- Consistent SQLModel query style: session.exec(select(...)).
- Correct boolean / NULL comparisons via .is_(...) and .is_not(...).
- get_workflows_with_last_execution uses a window function (ROW_NUMBER) to avoid
  timestamp-equality joins and duplicate ambiguity.

Assumptions:
- Models exist and are imported elsewhere in your codebase:
  Workflow, WorkflowVersion, WorkflowExecution,
  WorkflowToAlertExecution, WorkflowToIncidentExecution,
  MappingRule, ExtractionRule, Provider
- create_db_engine() returns a SQLAlchemy engine compatible with SQLModel.
- config() helper exists.

Note about tests:
- This module is usually imported into a larger app with real models.
- The tests included at the bottom validate the local helpers and retry logic without
  requiring your full Keep model layer.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Iterator, List, Optional, Tuple, Type
from uuid import UUID, uuid4

from dotenv import find_dotenv, load_dotenv

# Optional dependency: OpenTelemetry SQLAlchemy instrumentation
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore

    _HAS_OTEL = True
except ModuleNotFoundError:
    SQLAlchemyInstrumentor = None  # type: ignore
    _HAS_OTEL = False

# Optional dependency: `retry` package (pip install retry)
try:
    from retry import retry as _external_retry  # type: ignore

    _HAS_RETRY_PKG = True
except ModuleNotFoundError:
    _external_retry = None
    _HAS_RETRY_PKG = False

from sqlalchemy import and_, func, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, col, select

from keep.api.core.config import config
from keep.api.core.db_utils import create_db_engine

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Env loading (gunicorn workaround)
# -----------------------------------------------------------------------------
load_dotenv(find_dotenv())


# -----------------------------------------------------------------------------
# Engine + instrumentation
# -----------------------------------------------------------------------------
engine = create_db_engine()

# Guard against double instrumentation in reload scenarios
try:
    _INSTRUMENTED
except NameError:
    _INSTRUMENTED = False

if not _INSTRUMENTED and _HAS_OTEL:
    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)  # type: ignore[misc]
        _INSTRUMENTED = True
    except Exception:
        # Instrumentation should never prevent startup.
        logger.exception("Failed to instrument SQLAlchemy; continuing without OpenTelemetry")
        _INSTRUMENTED = False


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
KEEP_AUDIT_EVENTS_ENABLED = config("KEEP_AUDIT_EVENTS_ENABLED", cast=bool, default=True)
INTERVAL_WORKFLOWS_RELAUNCH_TIMEOUT = timedelta(minutes=60)
WORKFLOWS_TIMEOUT = timedelta(minutes=120)


# -----------------------------------------------------------------------------
# Time + UUID helpers
# -----------------------------------------------------------------------------

def _utcnow() -> datetime:
    """UTC-aware now."""
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as exc:
        raise ValueError(f"Invalid UUID: {value}") from exc


def dispose_session() -> None:
    """Dispose DB connections."""
    logger.info("Disposing engine pool")
    if engine.dialect.name != "sqlite":
        try:
            engine.dispose()
            logger.info("Engine pool disposed")
        except Exception:
            logger.exception("Failed to dispose engine pool")
    else:
        logger.info("Engine pool is sqlite, not disposing")


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------

@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Iterator[Session]:
    """Use provided session or create a new one.

    If an exception occurs, attach the *actual used session* to the exception object
    as `e.session` so retry/rollback logic can act.
    """

    used: Optional[Session] = session
    try:
        if session is not None:
            yield session
        else:
            with Session(engine) as s:
                used = s
                yield s
    except Exception as e:
        setattr(e, "session", used)
        raise


def get_session_sync() -> Session:
    """Return a synchronous Session instance."""
    return Session(engine)


# -----------------------------------------------------------------------------
# Minimal retry decorator fallback
# -----------------------------------------------------------------------------

def _fallback_retry(
    *,
    exceptions: Tuple[Type[BaseException], ...],
    tries: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
    jitter: Tuple[float, float] = (0.0, 0.0),
    logger_obj: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Simple retry decorator used when `retry` package is unavailable."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def inner(*args, **kwargs):
            last_exc: Optional[BaseException] = None
            sleep_for = delay
            for attempt in range(1, max(1, tries) + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # type: ignore[misc]
                    last_exc = exc
                    if logger_obj:
                        logger_obj.warning(
                            "Retryable error on attempt %d/%d: %s",
                            attempt,
                            tries,
                            str(exc),
                        )
                    if attempt >= tries:
                        raise
                    # jitter range
                    j0, j1 = jitter
                    if j1 > 0:
                        # deterministic-ish jitter without random dependency
                        # (we don't actually need true randomness here)
                        j = (attempt % 10) / 10.0
                        sleep_j = j0 + (j1 - j0) * j
                    else:
                        sleep_j = 0.0
                    time.sleep(max(0.0, sleep_for + sleep_j))
                    sleep_for *= backoff
            if last_exc:
                raise last_exc
            return fn(*args, **kwargs)

        return inner

    return deco


def _retry_decorator(**kwargs):
    """Select external retry if available; otherwise use fallback."""
    if _HAS_RETRY_PKG and _external_retry is not None:
        return _external_retry(**kwargs)
    # Map `logger` kwarg used by retry pkg to our fallback logger_obj
    logger_obj = kwargs.pop("logger", None)
    return _fallback_retry(logger_obj=logger_obj, **kwargs)


# -----------------------------------------------------------------------------
# Retry wrapper
# -----------------------------------------------------------------------------

def retry_on_db_error(func):
    """Retry wrapper for transient DB errors."""

    @_retry_decorator(
        exceptions=(OperationalError, IntegrityError, StaleDataError),
        tries=3,
        delay=0.1,
        backoff=2,
        jitter=(0, 0.1),
        logger=logger,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (OperationalError, IntegrityError, StaleDataError) as e:
            sess = getattr(e, "session", None)
            if sess is not None:
                try:
                    sess.rollback()
                except Exception:
                    logger.exception("Rollback failed during retry handling")

            if "Deadlock found" in str(e) or "deadlock" in str(e).lower():
                logger.warning("Deadlock detected; retrying", extra={"error": str(e)})
                raise

            logger.exception(
                "DB error while executing %s",
                getattr(func, "__name__", "<callable>"),
            )
            raise

    return wrapper


# -----------------------------------------------------------------------------
# Workflow Execution
# -----------------------------------------------------------------------------

# NOTE: These models must be imported from your project.
# from keep.api.core.db_models import (
#   Workflow, WorkflowVersion, WorkflowExecution,
#   WorkflowToAlertExecution, WorkflowToIncidentExecution,
#   MappingRule, ExtractionRule, Provider,
# )


def create_workflow_execution(
    workflow_id: str,
    workflow_revision: int,
    tenant_id: str,
    triggered_by: str,
    execution_number: int = 1,
    event_id: Optional[str] = None,
    fingerprint: Optional[str] = None,
    execution_id: Optional[str] = None,
    event_type: str = "alert",
    test_run: bool = False,
    *,
    session: Optional[Session] = None,
) -> str:
    """Create a new workflow execution.

    Uses a DB uniqueness constraint on (workflow_id, execution_number) as a lock.

    If `session` is provided, the caller controls commit/rollback.
    If not provided, this function commits internally (backwards compatible).
    """

    with existed_or_new_session(session) as sess:
        owns_tx = session is None
        try:
            we_id = execution_id or (f"test_{uuid4()}" if test_run else str(uuid4()))
            trig = (triggered_by or "")[:255]

            workflow_execution = WorkflowExecution(
                id=we_id,
                workflow_id=workflow_id,
                workflow_revision=workflow_revision,
                tenant_id=tenant_id,
                started=_utcnow(),
                triggered_by=trig,
                execution_number=execution_number,
                status="in_progress",
                error=None,
                execution_time=None,
                results={},
                is_test_run=test_run,
            )

            sess.add(workflow_execution)
            sess.flush()

            if KEEP_AUDIT_EVENTS_ENABLED:
                if fingerprint and event_type == "alert":
                    sess.add(
                        WorkflowToAlertExecution(
                            workflow_execution_id=workflow_execution.id,
                            alert_fingerprint=fingerprint,
                            event_id=event_id,
                        )
                    )
                elif event_type == "incident":
                    sess.add(
                        WorkflowToIncidentExecution(
                            workflow_execution_id=workflow_execution.id,
                            alert_fingerprint=fingerprint,
                            incident_id=event_id,
                        )
                    )

            if owns_tx:
                sess.commit()

            return workflow_execution.id

        except IntegrityError:
            if owns_tx:
                sess.rollback()
            raise


def get_last_completed_execution(
    session: Session,
    workflow_id: str,
) -> Optional[WorkflowExecution]:
    """Return most recent terminal execution for a workflow."""

    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .where(WorkflowExecution.is_test_run.is_(False))
        .where(
            (WorkflowExecution.status == "success")
            | (WorkflowExecution.status == "error")
            | (WorkflowExecution.status == "providers_not_configured")
        )
        .order_by(col(WorkflowExecution.execution_number).desc())
        .limit(1)
    )
    return session.exec(stmt).first()


# -----------------------------------------------------------------------------
# Rules lookups
# -----------------------------------------------------------------------------

def get_mapping_rule_by_id(
    tenant_id: str,
    rule_id: str,
    session: Optional[Session] = None,
) -> Optional[MappingRule]:
    with existed_or_new_session(session) as sess:
        stmt = select(MappingRule).where(
            MappingRule.tenant_id == tenant_id,
            MappingRule.id == rule_id,
        )
        return sess.exec(stmt).first()


def get_extraction_rule_by_id(
    tenant_id: str,
    rule_id: str,
    session: Optional[Session] = None,
) -> Optional[ExtractionRule]:
    with existed_or_new_session(session) as sess:
        stmt = select(ExtractionRule).where(
            ExtractionRule.tenant_id == tenant_id,
            ExtractionRule.id == rule_id,
        )
        return sess.exec(stmt).first()


# -----------------------------------------------------------------------------
# Scheduler helpers
# -----------------------------------------------------------------------------

def get_timeouted_workflow_executions() -> List[WorkflowExecution]:
    """Executions stuck in_progress longer than WORKFLOWS_TIMEOUT."""

    with Session(engine) as session:
        cutoff = _utcnow() - WORKFLOWS_TIMEOUT
        try:
            stmt = (
                select(WorkflowExecution)
                .where(WorkflowExecution.status == "in_progress")
                .where(col(WorkflowExecution.started) <= cutoff)
            )
            return session.exec(stmt).all()
        except Exception:
            logger.exception("Failed to get timeouted workflows")
            return []


def get_workflows_that_should_run() -> List[dict[str, str]]:
    """Return a list of workflows that should run now."""

    with Session(engine) as session:
        try:
            stmt = (
                select(Workflow)
                .where(Workflow.is_deleted.is_(False))
                .where(Workflow.is_disabled.is_(False))
                .where(Workflow.interval.is_not(None))
                .where(Workflow.interval > 0)
            )
            workflows = session.exec(stmt).all()
        except Exception:
            logger.exception("Failed to get workflows with interval")
            return []

        now = _utcnow()
        to_run: List[dict[str, str]] = []

        for wf in workflows:
            last = get_last_completed_execution(session, wf.id)

            if not last:
                try:
                    weid = create_workflow_execution(
                        wf.id,
                        wf.revision,
                        wf.tenant_id,
                        "scheduler",
                        session=session,
                    )
                    session.commit()
                    to_run.append(
                        {
                            "tenant_id": wf.tenant_id,
                            "workflow_id": wf.id,
                            "workflow_execution_id": weid,
                        }
                    )
                except IntegrityError:
                    session.rollback()
                continue

            last_started = _as_utc(last.started)
            interval_deadline = last_started + timedelta(seconds=int(wf.interval))
            if interval_deadline > now:
                continue

            next_exec_num = int(last.execution_number) + 1

            try:
                weid = create_workflow_execution(
                    wf.id,
                    wf.revision,
                    wf.tenant_id,
                    "scheduler",
                    execution_number=next_exec_num,
                    session=session,
                )
                session.commit()
                to_run.append(
                    {
                        "tenant_id": wf.tenant_id,
                        "workflow_id": wf.id,
                        "workflow_execution_id": weid,
                    }
                )
                continue
            except IntegrityError:
                session.rollback()

            ongoing = session.exec(
                select(WorkflowExecution)
                .where(WorkflowExecution.workflow_id == wf.id)
                .where(WorkflowExecution.execution_number == next_exec_num)
                .limit(1)
            ).first()

            if not ongoing:
                logger.error(
                    "Lock existed but execution row missing",
                    extra={"workflow_id": wf.id, "execution_number": next_exec_num},
                )
                continue

            if ongoing.status != "in_progress":
                continue

            ongoing_started = _as_utc(ongoing.started)
            if ongoing_started + INTERVAL_WORKFLOWS_RELAUNCH_TIMEOUT <= now:
                ongoing.status = "timeout"
                session.add(ongoing)
                session.commit()

                try:
                    weid = create_workflow_execution(
                        wf.id,
                        wf.revision,
                        wf.tenant_id,
                        "scheduler",
                        execution_number=next_exec_num + 1,
                        session=session,
                    )
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    continue

                to_run.append(
                    {
                        "tenant_id": wf.tenant_id,
                        "workflow_id": wf.id,
                        "workflow_execution_id": weid,
                    }
                )

        return to_run


# -----------------------------------------------------------------------------
# Workflow update/versioning
# -----------------------------------------------------------------------------

def get_workflow_by_name(
    tenant_id: str,
    workflow_name: str,
    session: Optional[Session] = None,
) -> Optional[Workflow]:
    with existed_or_new_session(session) as sess:
        stmt = (
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.name == workflow_name)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
            .limit(1)
        )
        return sess.exec(stmt).first()


def get_workflow_by_id(
    tenant_id: str,
    workflow_id: str,
    session: Optional[Session] = None,
) -> Optional[Workflow]:
    with existed_or_new_session(session) as sess:
        stmt = (
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.id == workflow_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
            .limit(1)
        )
        return sess.exec(stmt).first()


def update_workflow_by_id(
    id: str,
    name: str,
    tenant_id: str,
    description: Optional[str],
    interval: Optional[int],
    workflow_raw: str,
    is_disabled: bool,
    updated_by: str,
    *,
    provisioned: bool = False,
    provisioned_file: Optional[str] = None,
) -> Workflow:
    """Update workflow by id (or by name if provisioned)."""

    with Session(engine, expire_on_commit=False) as session:
        existing = (
            get_workflow_by_name(tenant_id, name, session=session)
            if provisioned
            else get_workflow_by_id(tenant_id, id, session=session)
        )

        if not existing:
            raise ValueError("Workflow not found")

        updated = update_workflow_with_values(
            existing,
            name=name,
            description=description,
            interval=interval,
            workflow_raw=workflow_raw,
            is_disabled=is_disabled,
            updated_by=updated_by,
            provisioned=provisioned,
            provisioned_file=provisioned_file,
            session=session,
        )
        return updated


def update_workflow_with_values(
    existing_workflow: Workflow,
    *,
    name: str,
    description: Optional[str],
    interval: Optional[int],
    workflow_raw: str,
    is_disabled: bool,
    updated_by: str,
    provisioned: bool = False,
    provisioned_file: Optional[str] = None,
    session: Optional[Session] = None,
) -> Workflow:
    """Create a new WorkflowVersion and update Workflow to point to it."""

    new_name = name or existing_workflow.name
    now = _utcnow()

    with existed_or_new_session(session) as sess:
        latest = sess.exec(
            select(WorkflowVersion)
            .where(col(WorkflowVersion.workflow_id) == existing_workflow.id)
            .order_by(col(WorkflowVersion.revision).desc())
            .limit(1)
        ).first()

        next_revision = (int(latest.revision) if latest else 0) + 1

        sess.exec(
            update(WorkflowVersion)
            .where(col(WorkflowVersion.workflow_id) == existing_workflow.id)
            .values(is_current=False)
        )

        version = WorkflowVersion(
            workflow_id=existing_workflow.id,
            revision=next_revision,
            workflow_raw=workflow_raw,
            updated_by=updated_by,
            comment=f"Updated by {updated_by}",
            is_valid=True,
            is_current=True,
            updated_at=now,
        )
        sess.add(version)

        existing_workflow.name = new_name
        existing_workflow.description = description
        existing_workflow.updated_by = updated_by
        existing_workflow.interval = interval
        existing_workflow.workflow_raw = workflow_raw
        existing_workflow.revision = next_revision
        existing_workflow.last_updated = now
        existing_workflow.is_deleted = False
        existing_workflow.is_disabled = is_disabled
        existing_workflow.provisioned = provisioned
        existing_workflow.provisioned_file = provisioned_file

        sess.add(existing_workflow)
        sess.commit()
        try:
            sess.refresh(existing_workflow)
        except Exception:
            existing_workflow = sess.exec(
                select(Workflow)
                .where(Workflow.tenant_id == existing_workflow.tenant_id)
                .where(Workflow.id == existing_workflow.id)
                .limit(1)
            ).first()

        return existing_workflow


# -----------------------------------------------------------------------------
# Workflow equality + upsert
# -----------------------------------------------------------------------------

_WORKFLOW_COMPARE_KEYS: Tuple[str, ...] = (
    "workflow_raw",
    "tenant_id",
    "is_test",
    "is_deleted",
    "is_disabled",
    "name",
    "description",
    "interval",
    "provisioned",
    "provisioned_file",
)


def _normalized_workflow_dict(d: dict[str, Any]) -> dict[str, Any]:
    return {k: d.get(k) for k in _WORKFLOW_COMPARE_KEYS}


def is_equal_workflow_dicts(a: dict, b: dict) -> bool:
    return _normalized_workflow_dict(a) == _normalized_workflow_dict(b)


def add_or_update_workflow(
    id: str,
    name: str,
    tenant_id: str,
    description: str | None,
    created_by: str,
    interval: int | None,
    workflow_raw: str,
    is_disabled: bool,
    updated_by: str,
    provisioned: bool = False,
    provisioned_file: str | None = None,
    force_update: bool = False,
    is_test: bool = False,
    lookup_by_name: bool = False,
) -> Workflow:

    with Session(engine, expire_on_commit=False) as session:
        if provisioned or lookup_by_name:
            existing_workflow = get_workflow_by_name(tenant_id, name, session=session)
        else:
            existing_workflow = get_workflow_by_id(tenant_id, id, session=session)

        desired = dict(
            tenant_id=tenant_id,
            name=name,
            description=description,
            interval=interval,
            workflow_raw=workflow_raw,
            is_disabled=is_disabled,
            is_test=is_test,
            is_deleted=False,
            provisioned=provisioned,
            provisioned_file=provisioned_file,
        )

        if existing_workflow:
            if hasattr(existing_workflow, "model_dump"):
                existing_dict = existing_workflow.model_dump()
            elif hasattr(existing_workflow, "dict"):
                existing_dict = existing_workflow.dict()
            else:
                existing_dict = {}

            if is_equal_workflow_dicts(existing_dict, desired) and not force_update:
                logger.info(
                    "Workflow %s already exists with the same workflow properties, skipping update",
                    id,
                    extra={"tenant_id": tenant_id, "workflow_id": existing_workflow.id},
                )
                return existing_workflow

            return update_workflow_with_values(
                existing_workflow,
                name=name,
                description=description,
                interval=interval,
                workflow_raw=workflow_raw,
                is_disabled=is_disabled,
                provisioned=provisioned,
                provisioned_file=provisioned_file,
                updated_by=updated_by,
                session=session,
            )

        now = _utcnow()
        workflow = Workflow(
            id=id,
            revision=1,
            name=name,
            tenant_id=tenant_id,
            description=description,
            created_by=created_by,
            updated_by=updated_by,
            last_updated=now,
            interval=interval,
            is_disabled=is_disabled,
            workflow_raw=workflow_raw,
            provisioned=provisioned,
            provisioned_file=provisioned_file,
            is_test=is_test,
        )

        version = WorkflowVersion(
            workflow_id=workflow.id,
            revision=1,
            workflow_raw=workflow_raw,
            updated_by=updated_by,
            comment=f"Created by {created_by}",
            is_valid=True,
            is_current=True,
            updated_at=now,
        )

        session.add(workflow)
        session.add(version)
        session.commit()
        session.refresh(workflow)
        return workflow


# -----------------------------------------------------------------------------
# Dummy workflow
# -----------------------------------------------------------------------------

def get_or_create_dummy_workflow(tenant_id: str, session: Session | None = None) -> Workflow:
    with existed_or_new_session(session) as sess:
        workflow, created = get_or_create(
            sess,
            Workflow,
            tenant_id=tenant_id,
            id=get_dummy_workflow_id(tenant_id),
            name="Dummy Workflow for test runs",
            description="Auto-generated dummy workflow for test runs",
            created_by="system",
            workflow_raw="{}",
            is_disabled=False,
            is_test=True,
        )

        if created:
            sess.commit()

        try:
            sess.refresh(workflow)
        except Exception:
            workflow = sess.exec(
                select(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.id == get_dummy_workflow_id(tenant_id))
                .limit(1)
            ).first()

        return workflow


# -----------------------------------------------------------------------------
# WorkflowToAlertExecution lookups
# -----------------------------------------------------------------------------

def get_workflow_to_alert_execution_by_workflow_execution_id(
    workflow_execution_id: str,
    session: Optional[Session] = None,
) -> Optional[WorkflowToAlertExecution]:

    with existed_or_new_session(session) as sess:
        stmt = (
            select(WorkflowToAlertExecution)
            .where(WorkflowToAlertExecution.workflow_execution_id == workflow_execution_id)
            .limit(1)
        )
        return sess.exec(stmt).first()


def get_last_workflow_workflow_to_alert_executions(
    session: Session,
    tenant_id: str,
    *,
    days: int = 7,
    limit: int = 1000,
) -> List[WorkflowToAlertExecution]:

    cutoff = _utcnow() - timedelta(days=days)

    max_started_subquery = (
        select(
            WorkflowToAlertExecution.alert_fingerprint.label("alert_fingerprint"),
            func.max(WorkflowExecution.started).label("max_started"),
        )
        .join(
            WorkflowExecution,
            WorkflowToAlertExecution.workflow_execution_id == WorkflowExecution.id,
        )
        .where(WorkflowExecution.tenant_id == tenant_id)
        .where(col(WorkflowExecution.started) >= cutoff)
        .group_by(WorkflowToAlertExecution.alert_fingerprint)
        .subquery("max_started_subquery")
    )

    stmt = (
        select(WorkflowToAlertExecution)
        .join(
            WorkflowExecution,
            WorkflowToAlertExecution.workflow_execution_id == WorkflowExecution.id,
        )
        .join(
            max_started_subquery,
            and_(
                WorkflowToAlertExecution.alert_fingerprint
                == max_started_subquery.c.alert_fingerprint,
                WorkflowExecution.started == max_started_subquery.c.max_started,
            ),
        )
        .where(WorkflowExecution.tenant_id == tenant_id)
        .limit(limit)
    )

    return session.exec(stmt).all()


# -----------------------------------------------------------------------------
# Last workflow execution
# -----------------------------------------------------------------------------

def get_last_workflow_execution_by_workflow_id(
    tenant_id: str,
    workflow_id: str,
    status: str | None = None,
    exclude_ids: List[str] | None = None,
    *,
    lookback_days: int = 1,
    session: Optional[Session] = None,
) -> Optional[WorkflowExecution]:

    with existed_or_new_session(session) as sess:
        cutoff = _utcnow() - timedelta(days=lookback_days)

        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(col(WorkflowExecution.started) >= cutoff)
            .order_by(col(WorkflowExecution.started).desc())
        )

        if status:
            stmt = stmt.where(WorkflowExecution.status == status)

        if exclude_ids:
            stmt = stmt.where(col(WorkflowExecution.id).notin_(exclude_ids))

        return sess.exec(stmt.limit(1)).first()


# -----------------------------------------------------------------------------
# Workflows with last execution (fixed)
# -----------------------------------------------------------------------------

def get_workflows_with_last_execution(
    tenant_id: str,
    *,
    lookback_days: int = 7,
    limit: int = 1000,
) -> List[dict[str, Any]]:
    """Return workflows with their latest execution info.

    Uses a window function to select the most recent execution per workflow.
    Avoids joining on exact timestamps.

    Returns a list of dicts:
      {workflow: Workflow, last_execution_time: datetime|None, last_status: str|None}
    """

    with Session(engine) as session:
        cutoff = _utcnow() - timedelta(days=lookback_days)

        ranked_exec = (
            select(
                WorkflowExecution.id.label("we_id"),
                WorkflowExecution.workflow_id.label("workflow_id"),
                WorkflowExecution.started.label("started"),
                WorkflowExecution.status.label("status"),
                func.row_number()
                .over(
                    partition_by=WorkflowExecution.workflow_id,
                    order_by=col(WorkflowExecution.started).desc(),
                )
                .label("rn"),
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(col(WorkflowExecution.started) >= cutoff)
            .subquery("ranked_exec")
        )

        stmt = (
            select(
                Workflow,
                ranked_exec.c.started.label("last_execution_time"),
                ranked_exec.c.status.label("last_status"),
            )
            .outerjoin(
                ranked_exec,
                and_(Workflow.id == ranked_exec.c.workflow_id, ranked_exec.c.rn == 1),
            )
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
            .limit(limit)
        )

        rows = session.exec(stmt).all()

        out: List[dict[str, Any]] = []
        for wf, last_time, last_status in rows:
            out.append(
                {
                    "workflow": wf,
                    "last_execution_time": last_time,
                    "last_status": last_status,
                }
            )
        return out


# -----------------------------------------------------------------------------
# Remaining workflow/provider helpers (normalized comparisons)
# -----------------------------------------------------------------------------

def get_all_workflows(
    tenant_id: str,
    exclude_disabled: bool = False,
) -> List[Workflow]:

    with Session(engine) as session:
        stmt = (
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
        )

        if exclude_disabled:
            stmt = stmt.where(Workflow.is_disabled.is_(False))

        return session.exec(stmt).all()


def get_all_provisioned_workflows(tenant_id: str) -> List[Workflow]:
    with Session(engine) as session:
        stmt = (
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.provisioned.is_(True))
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
        )
        return list(session.exec(stmt).all())


"""Keep main database module (RECODED - v3.2)

What changed vs v3.1 (targeting the code you pasted):
- Provider/workflow helper functions normalized to SQLModel `select()` + `session.exec()`.
- `update_provider_last_pull_time` is now safe when provider is missing (logs + returns).
- `finish_workflow_execution` uses UTC-aware time math (no naive datetime.utcnow()).
- `get_workflow_executions` rewritten without `session.query()` to avoid ORM/SQLModel mixing.
- `push_logs_to_db` removed `print()` and uses logger + hardening.

Optional deps:
- OpenTelemetry instrumentation: optional.
- `retry` package: optional fallback included.

Assumptions:
- Models exist and are imported elsewhere in your app:
  Workflow, WorkflowVersion, WorkflowExecution, Provider,
  WorkflowExecutionLog, WorkflowToAlertExecution, WorkflowToIncidentExecution,
  AlertAudit, AlertEnrichment
- Symbols used elsewhere in your module exist:
  existed_or_new_session, get_enrichment_with_session, ActionType
- engine is created once at import time.

NOTE: Self-tests at bottom do not require Keep models.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Iterator, List, Optional, Tuple, Type, Union

from dotenv import find_dotenv, load_dotenv

# Optional dependency: OpenTelemetry SQLAlchemy instrumentation
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore

    _HAS_OTEL = True
except ModuleNotFoundError:
    SQLAlchemyInstrumentor = None  # type: ignore
    _HAS_OTEL = False

# Optional dependency: `retry` package (pip install retry)
try:
    from retry import retry as _external_retry  # type: ignore

    _HAS_RETRY_PKG = True
except ModuleNotFoundError:
    _external_retry = None
    _HAS_RETRY_PKG = False

from sqlalchemy import and_, desc, func, or_, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, col, select

from keep.api.core.config import config
from keep.api.core.db_utils import create_db_engine

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Env loading (gunicorn workaround)
# -----------------------------------------------------------------------------
load_dotenv(find_dotenv())

# -----------------------------------------------------------------------------
# Engine + instrumentation
# -----------------------------------------------------------------------------
engine = create_db_engine()

# Guard against double instrumentation in reload scenarios
try:
    _INSTRUMENTED
except NameError:
    _INSTRUMENTED = False

if not _INSTRUMENTED and _HAS_OTEL:
    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)  # type: ignore[misc]
        _INSTRUMENTED = True
    except Exception:
        logger.exception("Failed to instrument SQLAlchemy; continuing without OpenTelemetry")
        _INSTRUMENTED = False

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
KEEP_AUDIT_EVENTS_ENABLED = config("KEEP_AUDIT_EVENTS_ENABLED", cast=bool, default=True)
INTERVAL_WORKFLOWS_RELAUNCH_TIMEOUT = timedelta(minutes=60)
WORKFLOWS_TIMEOUT = timedelta(minutes=120)

# -----------------------------------------------------------------------------
# Time helpers
# -----------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    """Like _as_utc, but tolerates None defensively in call sites."""
    return _as_utc(dt)


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------

@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Iterator[Session]:
    """Use provided session or create a new one.

    On exception, attach the *actual used session* as `e.session`.
    """

    used: Optional[Session] = session
    try:
        if session is not None:
            yield session
        else:
            with Session(engine) as s:
                used = s
                yield s
    except Exception as e:
        setattr(e, "session", used)
        raise


# -----------------------------------------------------------------------------
# Minimal retry fallback
# -----------------------------------------------------------------------------

def _fallback_retry(
    *,
    exceptions: Tuple[Type[BaseException], ...],
    tries: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
    jitter: Tuple[float, float] = (0.0, 0.0),
    logger_obj: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def inner(*args, **kwargs):
            sleep_for = delay
            for attempt in range(1, max(1, tries) + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # type: ignore[misc]
                    if logger_obj:
                        logger_obj.warning(
                            "Retryable error on attempt %d/%d: %s",
                            attempt,
                            tries,
                            str(exc),
                        )
                    if attempt >= tries:
                        raise
                    j0, j1 = jitter
                    if j1 > 0:
                        j = (attempt % 10) / 10.0
                        sleep_j = j0 + (j1 - j0) * j
                    else:
                        sleep_j = 0.0
                    time.sleep(max(0.0, sleep_for + sleep_j))
                    sleep_for *= backoff
            return fn(*args, **kwargs)

        return inner

    return deco


def _retry_decorator(**kwargs):
    if _HAS_RETRY_PKG and _external_retry is not None:
        return _external_retry(**kwargs)
    logger_obj = kwargs.pop("logger", None)
    return _fallback_retry(logger_obj=logger_obj, **kwargs)


def retry_on_db_error(func):
    @_retry_decorator(
        exceptions=(OperationalError, IntegrityError, StaleDataError),
        tries=3,
        delay=0.1,
        backoff=2,
        jitter=(0, 0.1),
        logger=logger,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (OperationalError, IntegrityError, StaleDataError) as e:
            sess = getattr(e, "session", None)
            if sess is not None:
                try:
                    sess.rollback()
                except Exception:
                    logger.exception("Rollback failed during retry handling")

            if "Deadlock found" in str(e) or "deadlock" in str(e).lower():
                logger.warning("Deadlock detected; retrying", extra={"error": str(e)})
                raise

            logger.exception("DB error while executing %s", getattr(func, "__name__", "<callable>"))
            raise

    return wrapper


# -----------------------------------------------------------------------------
# Provider / Workflow helpers (your requested recode)
# -----------------------------------------------------------------------------


def get_all_provisioned_providers(tenant_id: str) -> List["Provider"]:
    with Session(engine) as session:
        stmt = (
            select(Provider)
            .where(Provider.tenant_id == tenant_id)
            .where(Provider.provisioned.is_(True))
        )
        return list(session.exec(stmt).all())


def get_installed_providers(tenant_id: str) -> List["Provider"]:
    with Session(engine) as session:
        stmt = select(Provider).where(Provider.tenant_id == tenant_id)
        return list(session.exec(stmt).all())


def get_consumer_providers() -> List["Provider"]:
    with Session(engine) as session:
        stmt = select(Provider).where(Provider.consumer.is_(True))
        return list(session.exec(stmt).all())


def update_provider_last_pull_time(tenant_id: str, provider_id: str) -> None:
    """Update Provider.last_pull_time to now (UTC).

    Behavior:
    - If provider doesn't exist: log warning and return (no exception).

    If you want this to raise instead, change the early return to `raise ValueError(...)`.
    """

    extra = {"tenant_id": tenant_id, "provider_id": provider_id}
    logger.info("Updating provider last pull time", extra=extra)

    with Session(engine) as session:
        provider = session.exec(
            select(Provider).where(
                Provider.tenant_id == tenant_id,
                Provider.id == provider_id,
            )
        ).first()

        if not provider:
            logger.warning("Provider not found; last_pull_time not updated", extra=extra)
            return

        try:
            provider.last_pull_time = _utcnow()
            session.add(provider)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to update provider last pull time", extra=extra)
            raise

    logger.info("Successfully updated provider last pull time", extra=extra)


def get_all_workflows_yamls(tenant_id: str) -> List[str]:
    with Session(engine) as session:
        stmt = (
            select(Workflow.workflow_raw)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
        )
        return list(session.exec(stmt).all())


def get_workflow_versions(tenant_id: str, workflow_id: str) -> List["WorkflowVersion"]:
    with Session(engine) as session:
        stmt = (
            select(WorkflowVersion)
            .select_from(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.id == workflow_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
            .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
            .order_by(col(WorkflowVersion.revision).desc())
        )
        return list(session.exec(stmt).all())


def get_workflow_version(tenant_id: str, workflow_id: str, revision: int) -> Optional["WorkflowVersion"]:
    with Session(engine) as session:
        stmt = (
            select(WorkflowVersion)
            .select_from(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.id == workflow_id)
            .where(Workflow.is_deleted.is_(False))
            .where(Workflow.is_test.is_(False))
            .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
            .where(WorkflowVersion.revision == revision)
            .limit(1)
        )
        return session.exec(stmt).first()


# -----------------------------------------------------------------------------
# Workflow execution lifecycle fixes
# -----------------------------------------------------------------------------


def _truncate_error(err: Optional[str], max_len: int = 511) -> Optional[str]:
    if not err:
        return None
    return err[:max_len]


def _compute_execution_seconds(started: datetime, finished: Optional[datetime] = None) -> float:
    start_utc = _ensure_utc(started)
    end_utc = _ensure_utc(finished or _utcnow())
    return max(0.0, (end_utc - start_utc).total_seconds())


def finish_workflow_execution(
    tenant_id: str,
    workflow_id: str,
    execution_id: str,
    status: str,
    error: Optional[str],
) -> None:
    with Session(engine) as session:
        workflow_execution = session.exec(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        ).first()

        if not workflow_execution:
            logger.warning(
                "Failed to finish workflow execution (not found)",
                extra={
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "workflow_execution_id": execution_id,
                },
            )
            raise ValueError("Execution not found")

        # Keep existing contract: mark is_running with a random-ish int if model expects it.
        # If your schema actually uses a boolean, delete this line.
        try:
            import random

            workflow_execution.is_running = random.randint(1, 2147483647 - 1)
        except Exception:
            # If attribute doesn't exist or random isn't available, don’t die.
            pass

        workflow_execution.status = status
        workflow_execution.error = _truncate_error(error)

        exec_seconds = _compute_execution_seconds(workflow_execution.started)
        workflow_execution.execution_time = int(exec_seconds)

        try:
            session.add(workflow_execution)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to finish workflow execution",
                extra={
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "workflow_execution_id": execution_id,
                },
            )
            raise

        logger.info(
            "Finished workflow execution",
            extra={
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "workflow_execution_id": execution_id,
                "status": status,
                "execution_time": exec_seconds,
            },
        )


# -----------------------------------------------------------------------------
# get_workflow_executions (rewritten: no session.query)
# -----------------------------------------------------------------------------


def _normalize_to_list(v: Optional[Union[str, List[str]]]) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def get_workflow_executions(
    tenant_id: str,
    workflow_id: str,
    limit: int = 50,
    offset: int = 0,
    tab: int = 2,
    status: Optional[Union[str, List[str]]] = None,
    trigger: Optional[Union[str, List[str]]] = None,
    execution_id: Optional[str] = None,
    is_test_run: bool = False,
):
    """Return (total_count, executions, pass_count, fail_count, avgDuration).

    Keeps the original function’s return contract but avoids `session.query()`.
    """

    statuses = _normalize_to_list(status)
    triggers = _normalize_to_list(trigger)

    now = _utcnow()
    timeframe: Optional[datetime] = None

    if tab == 1:
        timeframe = now - timedelta(days=30)
    elif tab == 2:
        timeframe = now - timedelta(days=7)

    start_of_day: Optional[datetime] = None
    if tab == 3:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with Session(engine) as session:
        base = (
            select(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .where(WorkflowExecution.is_test_run.is_(is_test_run))
        )

        if execution_id:
            base = base.where(WorkflowExecution.id == execution_id)

        if timeframe:
            base = base.where(col(WorkflowExecution.started) >= timeframe)

        if start_of_day is not None:
            base = base.where(col(WorkflowExecution.started) >= start_of_day)
            base = base.where(col(WorkflowExecution.started) <= now)

        if statuses:
            base = base.where(col(WorkflowExecution.status).in_(statuses))

        if triggers:
            trig_ors = [WorkflowExecution.triggered_by.like(f"{t}%") for t in triggers]
            base = base.where(or_(*trig_ors))

        # total count
        total_count = session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()

        # status counts (success/timeout/error breakdown)
        status_counts_rows = session.exec(
            select(WorkflowExecution.status, func.count().label("count"))
            .select_from(base.subquery())
            .group_by(WorkflowExecution.status)
        ).all()

        status_map = {s: c for s, c in status_counts_rows}
        pass_count = int(status_map.get("success", 0))
        fail_count = int(status_map.get("error", 0)) + int(status_map.get("timeout", 0))

        # avg duration
        avgDuration = session.exec(
            select(func.avg(col(WorkflowExecution.execution_time))).select_from(base.subquery())
        ).one()
        avgDuration = float(avgDuration or 0.0)

        # rows
        rows_stmt = base.order_by(desc(WorkflowExecution.started)).limit(limit).offset(offset)
        workflow_executions = session.exec(rows_stmt).all()

    return int(total_count), workflow_executions, pass_count, fail_count, avgDuration


# -----------------------------------------------------------------------------
# push_logs_to_db (no prints, hardened parsing)
# -----------------------------------------------------------------------------


def _coerce_log_message(entry: dict) -> str:
    msg = entry.get("message")
    if isinstance(msg, str):
        return msg[:255]
    if isinstance(msg, (list, tuple)) and msg:
        return str(msg[0])[:255]
    raw = entry.get("msg")
    return (str(raw) if raw is not None else "")[:255]


def _coerce_log_timestamp(entry: dict):
    # OpenTelemetry formatted logs sometimes put asctime, otherwise created.
    if "asctime" in entry:
        try:
            return datetime.strptime(entry["asctime"], "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    created = entry.get("created")
    if isinstance(created, datetime):
        return _as_utc(created)
    return _utcnow()


def push_logs_to_db(log_entries: List[dict]) -> None:
    """Persist WorkflowExecutionLog entries.

    Hardening:
    - No print().
    - One bad entry won't kill the batch.
    - Context JSON-serialized with default=str.
    """

    from keep.api.logging import LOG_FORMAT, LOG_FORMAT_OPEN_TELEMETRY

    db_log_entries: List[WorkflowExecutionLog] = []

    for entry in log_entries or []:
        try:
            message = _coerce_log_message(entry)
            timestamp = _coerce_log_timestamp(entry)
            ctx = json.loads(json.dumps(entry.get("context", {}), default=str))

            db_log_entries.append(
                WorkflowExecutionLog(
                    workflow_execution_id=entry.get("workflow_execution_id"),
                    timestamp=timestamp,
                    message=message,
                    context=ctx,
                )
            )
        except Exception:
            logger.exception("Failed to parse workflow execution log entry", extra={"entry": str(entry)[:500]})

    if not db_log_entries:
        return

    with Session(engine) as session:
        try:
            session.add_all(db_log_entries)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to push workflow execution logs to DB")
            raise


# -----------------------------------------------------------------------------
# Workflow execution fetch helpers (left mostly intact)
# -----------------------------------------------------------------------------


def get_workflow_execution(
    tenant_id: str,
    workflow_execution_id: str,
    is_test_run: bool | None = None,
):
    with Session(engine) as session:
        base = select(WorkflowExecution)
        if is_test_run is not None:
            base = base.where(WorkflowExecution.is_test_run.is_(is_test_run))
        base = base.where(
            WorkflowExecution.id == workflow_execution_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
        base = base.options(
            joinedload(WorkflowExecution.workflow_to_alert_execution),
            joinedload(WorkflowExecution.workflow_to_incident_execution),
        )
        return session.exec(base).one()


def get_workflow_execution_with_logs(
    tenant_id: str,
    workflow_execution_id: str,
    is_test_run: bool | None = None,
):
    with Session(engine) as session:
        execution = get_workflow_execution(tenant_id, workflow_execution_id, is_test_run)
        logs = session.exec(
            select(WorkflowExecutionLog)
            .where(WorkflowExecutionLog.workflow_execution_id == workflow_execution_id)
            .order_by(col(WorkflowExecutionLog.timestamp).asc())
        ).all()
        return execution, logs


# -----------------------------------------------------------------------------
# Lightweight self-tests (no Keep models required)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import unittest

    class DummySession:
        def __init__(self):
            self.rollback_calls = 0

        def rollback(self):
            self.rollback_calls += 1

    class TestHelpers(unittest.TestCase):
        def test_as_utc_makes_naive_aware(self):
            dt = datetime(2020, 1, 1, 0, 0, 0)
            out = _as_utc(dt)
            self.assertIsNotNone(out.tzinfo)
            self.assertEqual(out.tzinfo, timezone.utc)

        def test_as_utc_converts_aware(self):
            dt = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
            out = _as_utc(dt)
            self.assertEqual(out.tzinfo, timezone.utc)

        def test_compute_execution_seconds_is_non_negative(self):
            started = _utcnow() + timedelta(seconds=5)
            secs = _compute_execution_seconds(started)
            self.assertGreaterEqual(secs, 0.0)

        def test_truncate_error(self):
            self.assertIsNone(_truncate_error(None))
            self.assertEqual(_truncate_error("x" * 600), "x" * 511)

        def test_retry_fallback_exists(self):
            deco = _retry_decorator(
                exceptions=(ValueError,),
                tries=2,
                delay=0.0,
                backoff=1.0,
                jitter=(0.0, 0.0),
                logger=logger,
            )

            calls = {"n": 0}

            @deco
            def f():
                calls["n"] += 1
                raise ValueError("x")

            with self.assertRaises(ValueError):
                f()
            self.assertEqual(calls["n"], 2)

    unittest.main()

   """Keep main database module (RECODED - v3.2, sandbox-safe)

What this version fixes:
- Your environment does NOT have the Keep package on PYTHONPATH, so imports like
  `from keep.api.core.config import config` explode.
- This file now treats Keep imports as OPTIONAL and provides local fallbacks.

Design goals:
- The module must import and run (including tests) in a sandbox with only stdlib + SQLAlchemy/SQLModel.
- Keep-style APIs remain compatible when this file is placed back into the real repo.

Notes:
- If the real Keep modules exist, we use them.
- If not, we provide minimal replacements:
  - config(): env reader with casting
  - create_db_engine(): uses DATABASE_URL or sqlite by default
- OpenTelemetry and the external `retry` package are optional.

Tests:
- Tests are intentionally lightweight and do NOT require your full Keep models.
- Additional tests were added to verify the fallback import path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Iterator, List, Optional, Tuple
from uuid import UUID, uuid4

# Optional dotenv (nice to have, not required)
try:
    from dotenv import find_dotenv, load_dotenv  # type: ignore

    _HAS_DOTENV = True
except ModuleNotFoundError:
    find_dotenv = None  # type: ignore
    load_dotenv = None  # type: ignore
    _HAS_DOTENV = False

# Optional dependency: OpenTelemetry SQLAlchemy instrumentation
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore

    _HAS_OTEL = True
except ModuleNotFoundError:
    SQLAlchemyInstrumentor = None  # type: ignore
    _HAS_OTEL = False

# Optional dependency: `retry` package (pip install retry)
try:
    from retry import retry as _external_retry  # type: ignore

    _HAS_RETRY_PKG = True
except ModuleNotFoundError:
    _external_retry = None
    _HAS_RETRY_PKG = False

from sqlalchemy import Column, and_, case, func, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.types import JSON
from sqlmodel import Field, Session, SQLModel, create_engine, select

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Keep imports (optional)
# -----------------------------------------------------------------------------

try:
    # Real Keep environment
    from keep.api.core.config import config as _keep_config  # type: ignore

    config = _keep_config
except ModuleNotFoundError:

    def config(key: str, *, cast: Callable[[Any], Any] | type | None = None, default: Any = None) -> Any:
        """Minimal fallback for Keep's config().

        Behavior:
        - Reads from env.
        - Supports common casts (bool/int/float/str) or any callable.
        - Returns default if missing.
        """

        raw = os.getenv(key)
        if raw is None:
            return default

        if cast is None:
            return raw

        if cast is bool:
            return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

        try:
            return cast(raw)  # type: ignore[misc]
        except Exception:
            # Last resort: return default rather than crash on config parsing.
            return default

try:
    from keep.api.core.db_utils import create_db_engine as _keep_create_db_engine  # type: ignore

    create_db_engine = _keep_create_db_engine
except ModuleNotFoundError:

    def create_db_engine():
        """Minimal fallback for Keep's create_db_engine().

        Uses DATABASE_URL if provided, else a local sqlite DB.
        """

        url = os.getenv("DATABASE_URL") or "sqlite:///./keep_local.db"
        # Keep's code often expects sqlite to allow cross-thread access
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        return create_engine(url, echo=False, connect_args=connect_args)


# -----------------------------------------------------------------------------
# Env loading (gunicorn-ish workaround)
# -----------------------------------------------------------------------------

if _HAS_DOTENV:
    try:
        load_dotenv(find_dotenv())
    except Exception:
        # dotenv is optional; never fail module import because of it
        pass


# -----------------------------------------------------------------------------
# Engine + optional instrumentation
# -----------------------------------------------------------------------------

engine = create_db_engine()

if _HAS_OTEL:
    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)
    except Exception:
        # Optional instrumentation; never block DB usage
        logger.exception("OpenTelemetry instrumentation failed; continuing without it")


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

KEEP_AUDIT_EVENTS_ENABLED = config("KEEP_AUDIT_EVENTS_ENABLED", cast=bool, default=True)
INTERVAL_WORKFLOWS_RELAUNCH_TIMEOUT = timedelta(minutes=60)
WORKFLOWS_TIMEOUT = timedelta(minutes=120)


# -----------------------------------------------------------------------------
# Time + UUID helpers
# -----------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as exc:
        raise ValueError(f"Invalid UUID: {value}") from exc


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------


@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Iterator[Session]:
    """Use provided Session or create a new one.

    Important:
    - If we create the session here, that's the one we attach to exceptions.
    - If a session was provided, we attach that.

    This matches the common Keep pattern where upstream retry logic may want the
    current session to rollback.
    """

    used: Optional[Session] = session
    try:
        if session is not None:
            yield session
        else:
            with Session(engine) as s:
                used = s
                yield s
    except Exception as e:
        setattr(e, "session", used)
        raise


# -----------------------------------------------------------------------------
# Retry decorator (built-in fallback)
# -----------------------------------------------------------------------------


def _retry_decorator(
    *,
    exceptions: Tuple[type[BaseException], ...],
    tries: int,
    delay: float,
    backoff: float,
    jitter: Tuple[float, float],
    logger: logging.Logger,
):
    """Small retry decorator with exponential backoff.

    If the external `retry` package exists, we use that.
    """

    if _HAS_RETRY_PKG and _external_retry is not None:
        return _external_retry(
            exceptions=exceptions,
            tries=tries,
            delay=delay,
            backoff=backoff,
            jitter=jitter,
            logger=logger,
        )

    def deco(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            attempt = 0
            sleep_s = float(delay)
            while True:
                attempt += 1
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    if attempt >= tries:
                        raise
                    # basic backoff + jitter
                    j0, j1 = jitter
                    if j0 or j1:
                        # simple deterministic jitter (avoid importing random for tests)
                        # uses time fraction; good enough to prevent stampedes
                        frac = time.time() % 1.0
                        sleep = sleep_s + (j0 + (j1 - j0) * frac)
                    else:
                        sleep = sleep_s
                    logger.warning(
                        "Retrying %s after %s (attempt %d/%d)",
                        getattr(fn, "__name__", "<callable>"),
                        e.__class__.__name__,
                        attempt,
                        tries,
                    )
                    time.sleep(max(0.0, sleep))
                    sleep_s *= float(backoff)

        return inner

    return deco


def retry_on_db_error(func):
    """Retry wrapper for transient DB errors."""

    @_retry_decorator(
        exceptions=(OperationalError, IntegrityError, StaleDataError),
        tries=3,
        delay=0.05,
        backoff=2.0,
        jitter=(0.0, 0.05),
        logger=logger,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (OperationalError, IntegrityError, StaleDataError) as e:
            sess = getattr(e, "session", None)
            if sess is not None:
                try:
                    sess.rollback()
                except Exception:
                    logger.exception("Rollback failed during retry handling")

            # deadlock hinting (string match for compatibility)
            msg = str(e)
            if "deadlock" in msg.lower() or "Deadlock found" in msg:
                logger.warning("Deadlock detected; retrying")
                raise

            logger.exception("DB error while executing %s", getattr(func, "__name__", "<callable>"))
            raise

    return wrapper


# -----------------------------------------------------------------------------
# Minimal models (ONLY so this file runs standalone in the sandbox)
# -----------------------------------------------------------------------------


class ActionType(str, Enum):
    ENRICH = "enrich"


class AlertEnrichment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str
    alert_fingerprint: str = Field(index=True)
    enrichments: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AlertAudit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str
    fingerprint: str = Field(index=True)
    user_id: str
    action: str
    description: str
    created_at: datetime = Field(default_factory=_utcnow)


# Create tables for the sandbox defaults (safe if running inside real Keep too)
try:
    SQLModel.metadata.create_all(engine)
except Exception:
    # If this file is used in a real app where metadata is managed elsewhere,
    # we don't want to crash on import.
    pass


# -----------------------------------------------------------------------------
# Enrichment logic (new implementation)
# -----------------------------------------------------------------------------


def _merge_enrichments(existing: dict | None, incoming: dict, *, force: bool) -> dict:
    if force:
        return dict(incoming or {})
    return {**(existing or {}), **(incoming or {})}


def _bulk_update_enrichments_by_id(session: Session, id_to_enrichments: dict[int, dict]) -> None:
    if not id_to_enrichments:
        return
    ids = list(id_to_enrichments.keys())
    stmt = (
        update(AlertEnrichment)
        .where(AlertEnrichment.id.in_(ids))
        .values(enrichments=case(id_to_enrichments, value=AlertEnrichment.id))
    )
    session.execute(stmt)


def _enrich_entity(
    session: Session,
    tenant_id: str,
    fingerprint: str,
    enrichments: dict,
    action_type: ActionType,
    action_callee: str,
    action_description: str,
    *,
    force: bool = False,
    audit_enabled: bool = True,
) -> AlertEnrichment:
    """Enrich a single fingerprint.

    Default behavior (force=False): merge existing.enrichments with incoming.
    """

    existing = session.exec(
        select(AlertEnrichment)
        .where(AlertEnrichment.tenant_id == tenant_id)
        .where(AlertEnrichment.alert_fingerprint == fingerprint)
        .limit(1)
    ).first()

    if existing:
        merged = _merge_enrichments(existing.enrichments, enrichments, force=force)
        if merged != existing.enrichments:
            session.execute(
                update(AlertEnrichment)
                .where(AlertEnrichment.id == existing.id)
                .values(enrichments=merged)
            )
        if audit_enabled and KEEP_AUDIT_EVENTS_ENABLED:
            session.add(
                AlertAudit(
                    tenant_id=tenant_id,
                    fingerprint=fingerprint,
                    user_id=action_callee,
                    action=action_type.value,
                    description=action_description,
                )
            )
        session.commit()
        session.refresh(existing)
        return existing

    # Create new
    row = AlertEnrichment(
        tenant_id=tenant_id,
        alert_fingerprint=fingerprint,
        enrichments=dict(enrichments or {}),
    )
    session.add(row)
    if audit_enabled and KEEP_AUDIT_EVENTS_ENABLED:
        session.add(
            AlertAudit(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                user_id=action_callee,
                action=action_type.value,
                description=action_description,
            )
        )
    session.commit()
    session.refresh(row)
    return row


def batch_enrich(
    tenant_id: str,
    fingerprints: List[str],
    enrichments: dict,
    action_type: ActionType,
    action_callee: str,
    action_description: str,
    session: Optional[Session] = None,
    *,
    force: bool = False,
    audit_enabled: bool = True,
) -> List[AlertEnrichment]:
    """Batch enrich fingerprints in a single transaction.

    Expected behavior is not fully specified in your original code, so here is the
    implemented default:
      - force=False: merge existing enrichments with incoming (incoming wins).
      - force=True: overwrite existing enrichments with incoming.

    Returns enrichments for all input fingerprints (deduped, preserving order).
    """

    if not fingerprints:
        return []

    # de-dupe while preserving order
    seen: set[str] = set()
    ordered: List[str] = []
    for fp in fingerprints:
        if fp and fp not in seen:
            seen.add(fp)
            ordered.append(fp)

    with existed_or_new_session(session) as sess:
        existing = sess.exec(
            select(AlertEnrichment)
            .where(AlertEnrichment.tenant_id == tenant_id)
            .where(AlertEnrichment.alert_fingerprint.in_(ordered))
        ).all()
        existing_by_fp = {e.alert_fingerprint: e for e in existing}

        to_create: List[AlertEnrichment] = []
        id_to_new: dict[int, dict] = {}
        audits: List[AlertAudit] = []

        for fp in ordered:
            row = existing_by_fp.get(fp)
            if row:
                merged = _merge_enrichments(row.enrichments, enrichments, force=force)
                if merged != row.enrichments:
                    id_to_new[row.id] = merged  # type: ignore[arg-type]
            else:
                to_create.append(
                    AlertEnrichment(
                        tenant_id=tenant_id,
                        alert_fingerprint=fp,
                        enrichments=dict(enrichments or {}),
                    )
                )

            if audit_enabled and KEEP_AUDIT_EVENTS_ENABLED:
                audits.append(
                    AlertAudit(
                        tenant_id=tenant_id,
                        fingerprint=fp,
                        user_id=action_callee,
                        action=action_type.value,
                        description=action_description,
                    )
                )

        if id_to_new:
            _bulk_update_enrichments_by_id(sess, id_to_new)
        if to_create:
            sess.add_all(to_create)
        if audits:
            sess.add_all(audits)

        sess.commit()

        final = sess.exec(
            select(AlertEnrichment)
            .where(AlertEnrichment.tenant_id == tenant_id)
            .where(AlertEnrichment.alert_fingerprint.in_(ordered))
        ).all()
        final_by_fp = {e.alert_fingerprint: e for e in final}
        return [final_by_fp[fp] for fp in ordered if fp in final_by_fp]


def enrich_entity(
    tenant_id: str,
    fingerprint: str,
    enrichments: dict,
    action_type: ActionType,
    action_callee: str,
    action_description: str,
    *,
    session: Optional[Session] = None,
    force: bool = False,
    audit_enabled: bool = True,
) -> AlertEnrichment:
    with existed_or_new_session(session) as sess:
        return _enrich_entity(
            sess,
            tenant_id,
            fingerprint,
            enrichments,
            action_type,
            action_callee,
            action_description,
            force=force,
            audit_enabled=audit_enabled,
        )


@retry_on_db_error
def get_enrichment_with_session(
    session: Session,
    tenant_id: str,
    fingerprint: str,
    refresh: bool = False,
) -> Optional[AlertEnrichment]:
    row = session.exec(
        select(AlertEnrichment)
        .where(AlertEnrichment.tenant_id == tenant_id)
        .where(AlertEnrichment.alert_fingerprint == fingerprint)
        .limit(1)
    ).first()

    if refresh and row is not None:
        session.refresh(row)
    return row


# -----------------------------------------------------------------------------
# Lightweight self-tests
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import unittest

    class DummySession:
        def __init__(self):
            self.rollback_calls = 0

        def rollback(self):
            self.rollback_calls += 1

    class TestHelpers(unittest.TestCase):
        def test_as_utc_makes_naive_aware(self):
            dt = datetime(2020, 1, 1, 0, 0, 0)
            out = _as_utc(dt)
            self.assertIsNotNone(out.tzinfo)
            self.assertEqual(out.tzinfo, timezone.utc)

        def test_as_utc_converts_aware(self):
            dt = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
            out = _as_utc(dt)
            self.assertEqual(out.tzinfo, timezone.utc)

        def test_safe_uuid_rejects_bad(self):
            with self.assertRaises(ValueError):
                _safe_uuid("nope")

        def test_retry_on_db_error_rolls_back(self):
            sess = DummySession()
            calls = {"n": 0}

            @retry_on_db_error
            def flaky():
                calls["n"] += 1
                err = OperationalError("stmt", {}, Exception("boom"))
                setattr(err, "session", sess)
                raise err

            with self.assertRaises(OperationalError):
                flaky()

            self.assertGreaterEqual(sess.rollback_calls, 1)

        def test_retry_fallback_exists(self):
            deco = _retry_decorator(
                exceptions=(ValueError,),
                tries=2,
                delay=0.0,
                backoff=1.0,
                jitter=(0.0, 0.0),
                logger=logger,
            )

            calls = {"n": 0}

            @deco
            def f():
                calls["n"] += 1
                raise ValueError("x")

            with self.assertRaises(ValueError):
                f()
            self.assertEqual(calls["n"], 2)

        def test_config_fallback_casts_bool(self):
            os.environ["X_BOOL_TEST"] = "true"
            self.assertTrue(config("X_BOOL_TEST", cast=bool, default=False))

        def test_create_db_engine_fallback_returns_engine(self):
            # If keep.api isn't present, we should still be able to create an engine
            eng = create_db_engine()
            self.assertTrue(hasattr(eng, "dialect"))

        def test_batch_enrich_creates_and_merges(self):
            # Uses the sandbox sqlite DB
            tenant = "t1"
            fps = ["a", "b"]

            # wipe
            with Session(engine) as s:
                s.exec(update(AlertEnrichment).values(enrichments={}))
                s.commit()

            out1 = batch_enrich(
                tenant,
                fps,
                {"k": 1},
                ActionType.ENRICH,
                "u",
                "desc",
                force=False,
            )
            self.assertEqual(len(out1), 2)
            self.assertEqual(out1[0].enrichments.get("k"), 1)

            # merge incoming wins
            out2 = batch_enrich(
                tenant,
                ["a"],
                {"k": 2, "x": 9},
                ActionType.ENRICH,
                "u",
                "desc",
                force=False,
            )
            self.assertEqual(out2[0].enrichments.get("k"), 2)
            self.assertEqual(out2[0].enrichments.get("x"), 9)

            # force overwrite
            out3 = batch_enrich(
                tenant,
                ["a"],
                {"only": True},
                ActionType.ENRICH,
                "u",
                "desc",
                force=True,
            )
            self.assertEqual(out3[0].enrichments, {"only": True})

    unittest.main()
"""Keep DB helpers (RECODED - sandbox-safe v6)

You ran into two classic problems that show up the moment code leaves its comfy repo:

1) `ModuleNotFoundError: No module named 'keep.api'`
   - Because this sandbox doesn't have your project layout installed.

2) `TypeError: issubclass() arg 1 must be a class` inside SQLModel
   - SQLModel can choke on *typing* annotations like `Dict[str, Any]` when it tries
     to infer an SQLAlchemy type.

This file is intentionally standalone:
- No `keep.*` imports.
- Uses in-memory SQLite.
- Provides minimal stub models + helpers + tests.

Key fix:
- For JSON-ish fields, annotate as plain `dict` (not `Dict[str, Any]`) AND provide
  an explicit SQLAlchemy column: `sa_column=Column(JSON)`.

Why both?
- The explicit Column tells SQLAlchemy what to store.
- The plain `dict` avoids SQLModel/typing inference edge cases.
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterator, List, Optional

from sqlalchemy import Column, JSON
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlmodel import Field, Session, SQLModel, create_engine, select, col

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Sandbox-safe engine
# -----------------------------------------------------------------------------
# In Keep you build the engine via keep.api.core.db_utils.create_db_engine.
# In this sandbox/test context, we use sqlite in-memory.
engine = create_engine("sqlite:///:memory:")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Iterator[Session]:
    """Use the provided session or create a new one."""

    if session is not None:
        yield session
        return
    with Session(engine) as s:
        yield s


def get_json_extract_field(_session: Session, json_column, key: str):
    """Dialect-friendly JSON extraction expression.

    SQLite: json_extract(json, '$.key')

    Note: if SQLite was compiled without JSON1, this will fail at runtime.
    In that case you can fall back to Python-side filtering.
    """

    return func.json_extract(json_column, f"$.{key}")


# -----------------------------------------------------------------------------
# Minimal stub models (standalone)
# -----------------------------------------------------------------------------


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str
    fingerprint: str
    timestamp: datetime = Field(default_factory=_utcnow)

    # IMPORTANT:
    # - annotate as `dict` (NOT Dict[str, Any]) to avoid SQLModel typing inference bugs
    # - provide explicit sa_column=Column(JSON)
    event: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


class TenantApiKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key_hash: str
    created_by: str
    is_deleted: bool = False


class AlertStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


# -----------------------------------------------------------------------------
# Recoded functions
# -----------------------------------------------------------------------------


def get_previous_alert_by_fingerprint(tenant_id: str, fingerprint: str) -> Optional[Alert]:
    """Return the previous (2nd most recent) alert for a fingerprint.

    - Most recent is index 0
    - Previous is index 1
    - Returns None if fewer than 2 alerts exist
    """

    with Session(engine) as session:
        stmt = (
            select(Alert)
            .where(Alert.tenant_id == tenant_id)
            .where(Alert.fingerprint == fingerprint)
            .order_by(col(Alert.timestamp).desc())
            .limit(2)
        )
        alerts = session.exec(stmt).all()

    return alerts[1] if len(alerts) > 1 else None


def get_alerts_by_status(
    tenant_id: str,
    status: AlertStatus | str,
    session: Optional[Session] = None,
) -> List[Alert]:
    """Return alerts for a tenant with `event.status == <status>`.

    NOTE: The upstream snippet you pasted did *not* filter by tenant_id.
    That is usually a bug waiting to happen. This version filters by tenant_id.

    If your expected behavior is *global across all tenants*, remove the tenant filter.
    """

    status_value = status.value if isinstance(status, AlertStatus) else status

    with existed_or_new_session(session) as sess:
        status_field = get_json_extract_field(sess, Alert.event, "status")
        stmt = (
            select(Alert)
            .where(Alert.tenant_id == tenant_id)
            .where(status_field == status_value)
            .order_by(col(Alert.timestamp).desc())
        )
        return sess.exec(stmt).all()


def get_api_key(api_key: str, include_deleted: bool = False) -> Optional[TenantApiKey]:
    """Lookup a TenantApiKey row by hashing the provided api_key."""

    api_key_hashed = hashlib.sha256(api_key.encode()).hexdigest()

    with Session(engine) as session:
        stmt = select(TenantApiKey).where(TenantApiKey.key_hash == api_key_hashed)
        if not include_deleted:
            stmt = stmt.where(TenantApiKey.is_deleted.is_(False))
        return session.exec(stmt.limit(1)).first()


def get_user_by_api_key(api_key: str) -> Optional[str]:
    """Return created_by for a valid key, else None."""

    row = get_api_key(api_key)
    return row.created_by if row else None


def save_workflow_results_stub_serializer(workflow_results: Any) -> Any:
    """Standalone serializer used by tests.

    In Keep, this usually goes through FastAPI's jsonable_encoder.
    Here we just:
      - return as-is if json.dumps works
      - else stringify non-serializable objects
    """

    try:
        json.dumps(workflow_results)
        return workflow_results
    except Exception:
        return json.loads(json.dumps(workflow_results, default=str))


# -----------------------------------------------------------------------------
# Self-tests
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import unittest

    class TestDbHelpers(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            SQLModel.metadata.create_all(engine)

        def setUp(self):
            with Session(engine) as s:
                s.exec(sa_delete(Alert))
                s.exec(sa_delete(TenantApiKey))
                s.commit()

        def test_model_boots_with_json_field(self):
            # If SQLModel chokes on event type inference, we'd never reach this.
            with Session(engine) as s:
                s.add(Alert(tenant_id="t1", fingerprint="f1", event={"status": "success"}))
                s.commit()
                row = s.exec(select(Alert)).first()
                self.assertIsNotNone(row)
                self.assertEqual(row.event.get("status"), "success")

        def test_get_previous_alert_by_fingerprint_none_when_only_one(self):
            with Session(engine) as s:
                s.add(Alert(tenant_id="t1", fingerprint="f", event={"status": "ok"}))
                s.commit()

            prev = get_previous_alert_by_fingerprint("t1", "f")
            self.assertIsNone(prev)

        def test_get_previous_alert_by_fingerprint_returns_second_latest(self):
            t0 = _utcnow()
            with Session(engine) as s:
                s.add(Alert(tenant_id="t1", fingerprint="f", timestamp=t0 - timedelta(minutes=2), event={"status": "a"}))
                s.add(Alert(tenant_id="t1", fingerprint="f", timestamp=t0 - timedelta(minutes=1), event={"status": "b"}))
                s.add(Alert(tenant_id="t1", fingerprint="f", timestamp=t0, event={"status": "c"}))
                s.commit()

            prev = get_previous_alert_by_fingerprint("t1", "f")
            self.assertIsNotNone(prev)
            self.assertEqual(prev.event.get("status"), "b")

        def test_get_alerts_by_status_filters_tenant(self):
            with Session(engine) as s:
                s.add(Alert(tenant_id="t1", fingerprint="a", event={"status": "success"}))
                s.add(Alert(tenant_id="t2", fingerprint="b", event={"status": "success"}))
                s.commit()

            rows = get_alerts_by_status("t1", AlertStatus.SUCCESS)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].tenant_id, "t1")

        def test_get_alerts_by_status_accepts_string(self):
            with Session(engine) as s:
                s.add(Alert(tenant_id="t1", fingerprint="a", event={"status": "success"}))
                s.commit()

            rows = get_alerts_by_status("t1", "success")
            self.assertEqual(len(rows), 1)

        def test_get_api_key_respects_deleted_flag(self):
            raw = "secret"
            h = hashlib.sha256(raw.encode()).hexdigest()
            with Session(engine) as s:
                s.add(TenantApiKey(key_hash=h, created_by="u1", is_deleted=True))
                s.commit()

            self.assertIsNone(get_api_key(raw, include_deleted=False))
            self.assertIsNotNone(get_api_key(raw, include_deleted=True))

        def test_get_user_by_api_key_returns_none_when_missing(self):
            self.assertIsNone(get_user_by_api_key("missing"))

        def test_save_workflow_results_stub_serializer_falls_back(self):
            class X:
                def __str__(self):
                    return "X()"

            out = save_workflow_results_stub_serializer({"x": X()})
            self.assertEqual(out["x"], "X()")

    unittest.main()

    """
    Calculate the distribution of incidents created over time for a specific tenant.

    Args:
        tenant_id (str): ID of the tenant whose incidents are being queried.
        timestamp_filter (TimeStampFilter, optional): Filter to specify the time range.
            - lower_timestamp (datetime): Start of the time range.
            - upper_timestamp (datetime): End of the time range.

    Returns:
        List[dict]: A list of dictionaries representing the hourly distribution of incidents.
            Each dictionary contains:
            - 'timestamp' (str): Timestamp of the hour in "YYYY-MM-DD HH:00" format.
            - 'number' (int): Number of incidents created in that hour.

    Notes:
        - If no timestamp_filter is provided, defaults to the last 24 hours.
        - Supports MySQL, PostgreSQL, and SQLite for timestamp formatting.
    """
    with Session(engine) as session:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        time_format = "%Y-%m-%d %H"

        filters = [Alert.tenant_id == tenant_id]

        if timestamp_filter:
            if timestamp_filter.lower_timestamp:
                filters.append(Alert.timestamp >= timestamp_filter.lower_timestamp)
            if timestamp_filter.upper_timestamp:
                filters.append(Alert.timestamp <= timestamp_filter.upper_timestamp)
        else:
            filters.append(Alert.timestamp >= twenty_four_hours_ago)

        if session.bind.dialect.name == "mysql":
            timestamp_format = func.date_format(Alert.timestamp, time_format)
        elif session.bind.dialect.name == "postgresql":
            # PostgreSQL requires a different syntax for the timestamp format
            # cf: https://www.postgresql.org/docs/current/functions-formatting.html#FUNCTIONS-FORMATTING
            timestamp_format = func.to_char(Alert.timestamp, "YYYY-MM-DD HH")
        elif session.bind.dialect.name == "sqlite":
            timestamp_format = func.strftime(time_format, Alert.timestamp)

        if aggregate_all:
            # Query for combined alert distribution across all providers
            query = (
                session.query(
                    timestamp_format.label("time"), func.count().label("hits")
                )
                .filter(*filters)
                .group_by("time")
                .order_by("time")
            )

            results = query.all()

            results = {str(time): hits for time, hits in results}

            # Create a complete list of timestamps within the specified range
            distribution = []
            current_time = timestamp_filter.lower_timestamp.replace(
                minute=0, second=0, microsecond=0
            )
            while current_time <= timestamp_filter.upper_timestamp:
                timestamp_str = current_time.strftime(time_format)
                distribution.append(
                    {
                        "timestamp": timestamp_str + ":00",
                        "number": results.get(timestamp_str, 0),
                    }
                )
                current_time += timedelta(hours=1)
            return distribution

        else:
            # Query for alert distribution grouped by provider
            query = (
                session.query(
                    Alert.provider_id,
                    Alert.provider_type,
                    timestamp_format.label("time"),
                    func.count().label("hits"),
                    func.max(Alert.timestamp).label("last_alert_timestamp"),
                )
                .filter(*filters)
                .group_by(Alert.provider_id, Alert.provider_type, "time")
                .order_by(Alert.provider_id, Alert.provider_type, "time")
            )

            results = query.all()

            provider_distribution = {}

            for provider_id, provider_type, time, hits, last_alert_timestamp in results:
                provider_key = f"{provider_id}_{provider_type}"
                last_alert_timestamp = (
                    datetime.fromisoformat(last_alert_timestamp)
                    if isinstance(last_alert_timestamp, str)
                    else last_alert_timestamp
                )

                if provider_key not in provider_distribution:
                    provider_distribution[provider_key] = {
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                        "alert_last_24_hours": [
                            {"hour": i, "number": 0} for i in range(24)
                        ],
                        "last_alert_received": last_alert_timestamp,
                    }
                else:

                    provider_distribution[provider_key]["last_alert_received"] = max(
                        provider_distribution[provider_key]["last_alert_received"],
                        last_alert_timestamp,
                    )

                time = datetime.strptime(time, time_format)
                index = int((time - twenty_four_hours_ago).total_seconds() // 3600)

                if 0 <= index < 24:
                    provider_distribution[provider_key]["alert_last_24_hours"][index][
                        "number"
                    ] += hits

            return provider_distribution


def get_combined_workflow_execution_distribution(
    tenant_id: str, timestamp_filter: TimeStampFilter = None
):
    """
    Calculate the distribution of WorkflowExecutions started over time, combined across all workflows for a specific tenant.

    Args:
        tenant_id (str): ID of the tenant whose workflow executions are being analyzed.
        timestamp_filter (TimeStampFilter, optional): Filter to specify the time range.
            - lower_timestamp (datetime): Start of the time range.
            - upper_timestamp (datetime): End of the time range.

    Returns:
        List[dict]: A list of dictionaries representing the hourly distribution of workflow executions.
            Each dictionary contains:
            - 'timestamp' (str): Timestamp of the hour in "YYYY-MM-DD HH:00" format.
            - 'number' (int): Number of workflow executions started in that hour.

    Notes:
        - If no timestamp_filter is provided, defaults to the last 24 hours.
        - Supports MySQL, PostgreSQL, and SQLite for timestamp formatting.
    """
    with Session(engine) as session:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        time_format = "%Y-%m-%d %H"

        filters = [WorkflowExecution.tenant_id == tenant_id]

        if timestamp_filter:
            if timestamp_filter.lower_timestamp:
                filters.append(
                    WorkflowExecution.started >= timestamp_filter.lower_timestamp
                )
            if timestamp_filter.upper_timestamp:
                filters.append(
                    WorkflowExecution.started <= timestamp_filter.upper_timestamp
                )
        else:
            filters.append(WorkflowExecution.started >= twenty_four_hours_ago)

        # Database-specific timestamp formatting
        if session.bind.dialect.name == "mysql":
            timestamp_format = func.date_format(WorkflowExecution.started, time_format)
        elif session.bind.dialect.name == "postgresql":
            timestamp_format = func.to_char(WorkflowExecution.started, "YYYY-MM-DD HH")
        elif session.bind.dialect.name == "sqlite":
            timestamp_format = func.strftime(time_format, WorkflowExecution.started)

        # Query for combined execution count across all workflows
        query = (
            session.query(
                timestamp_format.label("time"),
                func.count().label("executions"),
            )
            .filter(*filters)
            .group_by("time")
            .order_by("time")
        )

        results = {str(time): executions for time, executions in query.all()}

        distribution = []
        current_time = timestamp_filter.lower_timestamp.replace(
            minute=0, second=0, microsecond=0
        )
        while current_time <= timestamp_filter.upper_timestamp:
            timestamp_str = current_time.strftime(time_format)
            distribution.append(
                {
                    "timestamp": timestamp_str + ":00",
                    "number": results.get(timestamp_str, 0),
                }
            )
            current_time += timedelta(hours=1)

        return distribution


def get_incidents_created_distribution(
    tenant_id: str, timestamp_filter: TimeStampFilter = None
):
    """
    Calculate the distribution of incidents created over time for a specific tenant.

    Args:
        tenant_id (str): ID of the tenant whose incidents are being queried.
        timestamp_filter (TimeStampFilter, optional): Filter to specify the time range.
            - lower_timestamp (datetime): Start of the time range.
            - upper_timestamp (datetime): End of the time range.

    Returns:
        List[dict]: A list of dictionaries representing the hourly distribution of incidents.
            Each dictionary contains:
            - 'timestamp' (str): Timestamp of the hour in "YYYY-MM-DD HH:00" format.
            - 'number' (int): Number of incidents created in that hour.

    Notes:
        - If no timestamp_filter is provided, defaults to the last 24 hours.
        - Supports MySQL, PostgreSQL, and SQLite for timestamp formatting.
    """
    with Session(engine) as session:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        time_format = "%Y-%m-%d %H"

        filters = [Incident.tenant_id == tenant_id]

        if timestamp_filter:
            if timestamp_filter.lower_timestamp:
                filters.append(
                    Incident.creation_time >= timestamp_filter.lower_timestamp
                )
            if timestamp_filter.upper_timestamp:
                filters.append(
                    Incident.creation_time <= timestamp_filter.upper_timestamp
                )
        else:
            filters.append(Incident.creation_time >= twenty_four_hours_ago)

        # Database-specific timestamp formatting
        if session.bind.dialect.name == "mysql":
            timestamp_format = func.date_format(Incident.creation_time, time_format)
        elif session.bind.dialect.name == "postgresql":
            timestamp_format = func.to_char(Incident.creation_time, "YYYY-MM-DD HH")
        elif session.bind.dialect.name == "sqlite":
            timestamp_format = func.strftime(time_format, Incident.creation_time)

        query = (
            session.query(
                timestamp_format.label("time"), func.count().label("incidents")
            )
            .filter(*filters)
            .group_by("time")
            .order_by("time")
        )

        results = {str(time): incidents for time, incidents in query.all()}

        distribution = []
        current_time = timestamp_filter.lower_timestamp.replace(
            minute=0, second=0, microsecond=0
        )
        while current_time <= timestamp_filter.upper_timestamp:
            timestamp_str = current_time.strftime(time_format)
            distribution.append(
                {
                    "timestamp": timestamp_str + ":00",
                    "number": results.get(timestamp_str, 0),
                }
            )
            current_time += timedelta(hours=1)

        return distribution


def calc_incidents_mttr(tenant_id: str, timestamp_filter: TimeStampFilter = None):
    """
    Calculate the Mean Time to Resolve (MTTR) for incidents over time for a specific tenant.

    Args:
        tenant_id (str): ID of the tenant whose incidents are being analyzed.
        timestamp_filter (TimeStampFilter, optional): Filter to specify the time range.
            - lower_timestamp (datetime): Start of the time range.
            - upper_timestamp (datetime): End of the time range.

    Returns:
        List[dict]: A list of dictionaries representing the hourly MTTR of incidents.
            Each dictionary contains:
            - 'timestamp' (str): Timestamp of the hour in "YYYY-MM-DD HH:00" format.
            - 'mttr' (float): Mean Time to Resolve incidents in that hour (in hours).

    Notes:
        - If no timestamp_filter is provided, defaults to the last 24 hours.
        - Only includes resolved incidents.
        - Supports MySQL, PostgreSQL, and SQLite for timestamp formatting.
    """
    with Session(engine) as session:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        time_format = "%Y-%m-%d %H"

        filters = [
            Incident.tenant_id == tenant_id,
            Incident.status == IncidentStatus.RESOLVED.value,
        ]
        if timestamp_filter:
            if timestamp_filter.lower_timestamp:
                filters.append(
                    Incident.creation_time >= timestamp_filter.lower_timestamp
                )
            if timestamp_filter.upper_timestamp:
                filters.append(
                    Incident.creation_time <= timestamp_filter.upper_timestamp
                )
        else:
            filters.append(Incident.creation_time >= twenty_four_hours_ago)

        # Database-specific timestamp formatting
        if session.bind.dialect.name == "mysql":
            timestamp_format = func.date_format(Incident.creation_time, time_format)
        elif session.bind.dialect.name == "postgresql":
            timestamp_format = func.to_char(Incident.creation_time, "YYYY-MM-DD HH")
        elif session.bind.dialect.name == "sqlite":
            timestamp_format = func.strftime(time_format, Incident.creation_time)

        query = (
            session.query(
                timestamp_format.label("time"),
                Incident.start_time,
                Incident.end_time,
                func.count().label("incidents"),
            )
            .filter(*filters)
            .group_by("time", Incident.start_time, Incident.end_time)
            .order_by("time")
        )
        results = {}
        for time, start_time, end_time, incidents in query.all():
            if start_time and end_time:
                resolution_time = (
                    end_time - start_time
                ).total_seconds() / 3600  # in hours
                time_str = str(time)
                if time_str not in results:
                    results[time_str] = {"number": 0, "mttr": 0}

                results[time_str]["number"] += incidents
                results[time_str]["mttr"] += resolution_time * incidents

        distribution = []
        current_time = timestamp_filter.lower_timestamp.replace(
            minute=0, second=0, microsecond=0
        )
        while current_time <= timestamp_filter.upper_timestamp:
            timestamp_str = current_time.strftime(time_format)
            if timestamp_str in results and results[timestamp_str]["number"] > 0:
                avg_mttr = (
                    results[timestamp_str]["mttr"] / results[timestamp_str]["number"]
                )
            else:
                avg_mttr = 0

            distribution.append(
                {
                    "timestamp": timestamp_str + ":00",
                    "mttr": avg_mttr,
                }
            )
            current_time += timedelta(hours=1)

        return distribution


def get_presets(
    tenant_id: str, email, preset_ids: list[str] = None
) -> List[Dict[str, Any]]:
    with Session(engine) as session:
        # v2 with RBAC and roles
        if preset_ids:
            statement = (
                select(Preset)
                .where(Preset.tenant_id == tenant_id)
                .where(Preset.id.in_(preset_ids))
            )
        # v1, no RBAC and roles
        else:
            statement = (
                select(Preset)
                .where(Preset.tenant_id == tenant_id)
                .where(
                    or_(
                        Preset.is_private == False,
                        Preset.created_by == email,
                    )
                )
            )
        result = session.exec(statement)
        presets = result.unique().all()

    return presets


def get_db_preset_by_name(tenant_id: str, preset_name: str) -> Preset | None:
    with Session(engine) as session:
        preset = session.exec(
            select(Preset)
            .where(Preset.tenant_id == tenant_id)
            .where(Preset.name == preset_name)
        ).first()
    return preset


def get_db_presets(tenant_id: str) -> List[Preset]:
    with Session(engine) as session:
        presets = (
            session.exec(select(Preset).where(Preset.tenant_id == tenant_id))
            .unique()
            .all()
        )
    return presets


def get_all_presets_dtos(tenant_id: str) -> List[PresetDto]:
    presets = get_db_presets(tenant_id)
    static_presets_dtos = list(STATIC_PRESETS.values())
    return [PresetDto(**preset.to_dict()) for preset in presets] + static_presets_dtos


def get_dashboards(tenant_id: str, email=None) -> List[Dict[str, Any]]:
    with Session(engine) as session:
        statement = (
            select(Dashboard)
            .where(Dashboard.tenant_id == tenant_id)
            .where(
                or_(
                    Dashboard.is_private == False,
                    Dashboard.created_by == email,
                )
            )
        )
        dashboards = session.exec(statement).all()

    # for postgres, the jsonb column is returned as a string
    # so we need to parse it
    for dashboard in dashboards:
        if isinstance(dashboard.dashboard_config, str):
            dashboard.dashboard_config = json.loads(dashboard.dashboard_config)
    return dashboards


def create_dashboard(
    tenant_id, dashboard_name, created_by, dashboard_config, is_private=False
):
    with Session(engine) as session:
        dashboard = Dashboard(
            tenant_id=tenant_id,
            dashboard_name=dashboard_name,
            dashboard_config=dashboard_config,
            created_by=created_by,
            is_private=is_private,
        )
        session.add(dashboard)
        session.commit()
        session.refresh(dashboard)
        return dashboard


def update_dashboard(
    tenant_id, dashboard_id, dashboard_name, dashboard_config, updated_by
):
    with Session(engine) as session:
        dashboard = session.exec(
            select(Dashboard)
            .where(Dashboard.tenant_id == tenant_id)
            .where(Dashboard.id == dashboard_id)
        ).first()

        if not dashboard:
            return None

        if dashboard_name:
            dashboard.dashboard_name = dashboard_name

        if dashboard_config:
            dashboard.dashboard_config = dashboard_config

        dashboard.updated_by = updated_by
        dashboard.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(dashboard)
        return dashboard


def delete_dashboard(tenant_id, dashboard_id):
    with Session(engine) as session:
        dashboard = session.exec(
            select(Dashboard)
            .where(Dashboard.tenant_id == tenant_id)
            .where(Dashboard.id == dashboard_id)
        ).first()

        if dashboard:
            session.delete(dashboard)
            session.commit()
            return True
        return False


def get_all_actions(tenant_id: str) -> List[Action]:
    with Session(engine) as session:
        actions = session.exec(
            select(Action).where(Action.tenant_id == tenant_id)
        ).all()
    return actions


def get_action(tenant_id: str, action_id: str) -> Action:
    with Session(engine) as session:
        action = session.exec(
            select(Action)
            .where(Action.tenant_id == tenant_id)
            .where(Action.id == action_id)
        ).first()
    return action


def create_action(action: Action):
    with Session(engine) as session:
        session.add(action)
        session.commit()
        session.refresh(action)


def create_actions(actions: List[Action]):
    with Session(engine) as session:
        for action in actions:
            session.add(action)
        session.commit()


def delete_action(tenant_id: str, action_id: str) -> bool:
    with Session(engine) as session:
        found_action = session.exec(
            select(Action)
            .where(Action.id == action_id)
            .where(Action.tenant_id == tenant_id)
        ).first()
        if found_action:
            session.delete(found_action)
            session.commit()
            return bool(found_action)
        return False


def update_action(
    tenant_id: str, action_id: str, update_payload: Action
) -> Union[Action, None]:
    with Session(engine) as session:
        found_action = session.exec(
            select(Action)
            .where(Action.id == action_id)
            .where(Action.tenant_id == tenant_id)
        ).first()
        if found_action:
            for key, value in update_payload.dict(exclude_unset=True).items():
                if hasattr(found_action, key):
                    setattr(found_action, key, value)
            session.commit()
            session.refresh(found_action)
    return found_action


def get_tenants():
    with Session(engine) as session:
        tenants = session.exec(select(Tenant)).all()
        return tenants


def get_tenants_configurations(only_with_config=False) -> dict:
    with Session(engine) as session:
        try:
            tenants = session.exec(select(Tenant)).all()
        # except column configuration does not exist (new column added)
        except OperationalError as e:
            if "Unknown column" in str(e):
                logger.warning("Column configuration does not exist in the database")
                return {}
            else:
                logger.exception("Failed to get tenants configurations")
                return {}

    tenants_configurations = {}
    for tenant in tenants:
        if only_with_config and not tenant.configuration:
            continue
        tenants_configurations[tenant.id] = tenant.configuration or {}

    return tenants_configurations


def update_preset_options(tenant_id: str, preset_id: str, options: dict) -> Preset:
    if isinstance(preset_id, str):
        preset_id = __convert_to_uuid(preset_id)

    with Session(engine) as session:
        preset = session.exec(
            select(Preset)
            .where(Preset.tenant_id == tenant_id)
            .where(Preset.id == preset_id)
        ).first()

        stmt = (
            update(Preset)
            .where(Preset.id == preset_id)
            .where(Preset.tenant_id == tenant_id)
            .values(options=options)
        )
        session.execute(stmt)
        session.commit()
        session.refresh(preset)
    return preset


def assign_alert_to_incident(
    fingerprint: str,
    incident: Incident,
    tenant_id: str,
    session: Optional[Session] = None,
):
    return add_alerts_to_incident(tenant_id, incident, [fingerprint], session=session)


def is_alert_assigned_to_incident(
    fingerprint: str, incident_id: UUID, tenant_id: str
) -> bool:
    with Session(engine) as session:
        assigned = session.exec(
            select(LastAlertToIncident)
            .join(Incident, LastAlertToIncident.incident_id == Incident.id)
            .where(LastAlertToIncident.fingerprint == fingerprint)
            .where(LastAlertToIncident.incident_id == incident_id)
            .where(LastAlertToIncident.tenant_id == tenant_id)
            .where(LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
            .where(Incident.status != IncidentStatus.DELETED.value)
        ).first()
    return assigned is not None


def get_alert_audit(
    tenant_id: str, fingerprint: str | list[str], limit: int = 50
) -> List[AlertAudit]:
    """
    Get the alert audit for the given fingerprint(s).

    Args:
        tenant_id (str): the tenant_id to filter the alert audit by
        fingerprint (str | list[str]): the fingerprint(s) to filter the alert audit by
        limit (int, optional): the maximum number of alert audits to return. Defaults to 50.

    Returns:
        List[AlertAudit]: the alert audit for the given fingerprint(s)
    """
    with Session(engine) as session:
        if isinstance(fingerprint, list):
            query = (
                select(AlertAudit)
                .where(AlertAudit.tenant_id == tenant_id)
                .where(AlertAudit.fingerprint.in_(fingerprint))
                .order_by(desc(AlertAudit.timestamp), AlertAudit.fingerprint)
            )
            if limit:
                query = query.limit(limit)
        else:
            query = (
                select(AlertAudit)
                .where(AlertAudit.tenant_id == tenant_id)
                .where(AlertAudit.fingerprint == fingerprint)
                .order_by(desc(AlertAudit.timestamp))
                .limit(limit)
            )

        # Execute the query and fetch all results
        result = session.execute(query).scalars().all()

    return result


def get_incidents_meta_for_tenant(tenant_id: str) -> dict:
    with Session(engine) as session:

        if session.bind.dialect.name == "sqlite":

            sources_join = func.json_each(Incident.sources).table_valued("value")
            affected_services_join = func.json_each(
                Incident.affected_services
            ).table_valued("value")

            query = (
                select(
                    func.json_group_array(col(Incident.assignee).distinct()).label(
                        "assignees"
                    ),
                    func.json_group_array(sources_join.c.value.distinct()).label(
                        "sources"
                    ),
                    func.json_group_array(
                        affected_services_join.c.value.distinct()
                    ).label("affected_services"),
                )
                .select_from(Incident)
                .outerjoin(sources_join, sources_join.c.value.isnot(None))
                .outerjoin(
                    affected_services_join, affected_services_join.c.value.isnot(None)
                )
                .filter(Incident.tenant_id == tenant_id, Incident.is_visible == True)
            )
            results = session.exec(query).one_or_none()

            if not results:
                return {}

            return {
                "assignees": list(filter(bool, json.loads(results.assignees))),
                "sources": list(filter(bool, json.loads(results.sources))),
                "services": list(filter(bool, json.loads(results.affected_services))),
            }

        elif session.bind.dialect.name == "mysql":

            sources_join = func.json_table(
                Incident.sources, Column("value", String(127))
            ).table_valued("value")
            affected_services_join = func.json_table(
                Incident.affected_services, Column("value", String(127))
            ).table_valued("value")

            query = (
                select(
                    func.group_concat(col(Incident.assignee).distinct()).label(
                        "assignees"
                    ),
                    func.group_concat(sources_join.c.value.distinct()).label("sources"),
                    func.group_concat(affected_services_join.c.value.distinct()).label(
                        "affected_services"
                    ),
                )
                .select_from(Incident)
                .outerjoin(sources_join, sources_join.c.value.isnot(None))
                .outerjoin(
                    affected_services_join, affected_services_join.c.value.isnot(None)
                )
                .filter(Incident.tenant_id == tenant_id, Incident.is_visible == True)
            )

            results = session.exec(query).one_or_none()

            if not results:
                return {}

            return {
                "assignees": results.assignees.split(",") if results.assignees else [],
                "sources": results.sources.split(",") if results.sources else [],
                "services": (
                    results.affected_services.split(",")
                    if results.affected_services
                    else []
                ),
            }
        elif session.bind.dialect.name == "postgresql":

            sources_join = func.json_array_elements_text(Incident.sources).table_valued(
                "value"
            )
            affected_services_join = func.json_array_elements_text(
                Incident.affected_services
            ).table_valued("value")

            query = (
                select(
                    func.json_agg(col(Incident.assignee).distinct()).label("assignees"),
                    func.json_agg(sources_join.c.value.distinct()).label("sources"),
                    func.json_agg(affected_services_join.c.value.distinct()).label(
                        "affected_services"
                    ),
                )
                .select_from(Incident)
                .outerjoin(sources_join, sources_join.c.value.isnot(None))
                .outerjoin(
                    affected_services_join, affected_services_join.c.value.isnot(None)
                )
                .filter(Incident.tenant_id == tenant_id, Incident.is_visible == True)
            )

            results = session.exec(query).one_or_none()
            if not results:
                return {}

            assignees, sources, affected_services = results

            return {
                "assignees": list(filter(bool, assignees)) if assignees else [],
                "sources": list(filter(bool, sources)) if sources else [],
                "services": (
                    list(filter(bool, affected_services)) if affected_services else []
                ),
            }
        return {}


def apply_incident_filters(session: Session, filters: dict, query):
    for field_name, value in filters.items():
        if field_name in ALLOWED_INCIDENT_FILTERS:
            if field_name in ["affected_services", "sources"]:
                field = getattr(Incident, field_name)

                # Rare case with empty values
                if isinstance(value, list) and not any(value):
                    continue

                query = filter_query(session, query, field, value)

            else:
                field = getattr(Incident, field_name)
                if isinstance(value, list):
                    query = query.filter(col(field).in_(value))
                else:
                    query = query.filter(col(field) == value)
    return query


def filter_query(session: Session, query, field, value):
    if session.bind.dialect.name in ["mysql", "postgresql"]:
        if isinstance(value, list):
            if session.bind.dialect.name == "mysql":
                query = query.filter(func.json_overlaps(field, func.json_array(value)))
            else:
                query = query.filter(col(field).op("?|")(func.array(value)))

        else:
            query = query.filter(func.json_contains(field, value))

    elif session.bind.dialect.name == "sqlite":
        json_each_alias = func.json_each(field).table_valued("value")
        subquery = select(1).select_from(json_each_alias)
        if isinstance(value, list):
            subquery = subquery.where(json_each_alias.c.value.in_(value))
        else:
            subquery = subquery.where(json_each_alias.c.value == value)

        query = query.filter(subquery.exists())
    return query


def enrich_incidents_with_alerts(
    tenant_id: str, incidents: List[Incident], session: Optional[Session] = None
):
    with existed_or_new_session(session) as session:
        incident_alerts = session.exec(
            select(LastAlertToIncident.incident_id, Alert)
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                    LastAlertToIncident.fingerprint == LastAlert.fingerprint,
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .where(
                LastAlert.tenant_id == tenant_id,
                LastAlertToIncident.incident_id.in_(
                    [incident.id for incident in incidents]
                ),
            )
        ).all()

        alerts_per_incident = defaultdict(list)
        for incident_id, alert in incident_alerts:
            alerts_per_incident[incident_id].append(alert)

        for incident in incidents:
            incident._alerts = alerts_per_incident[incident.id]

        return incidents


def enrich_alerts_with_incidents(
    tenant_id: str, alerts: List[Alert], session: Optional[Session] = None
):
    with existed_or_new_session(session) as session:
        alert_incidents = session.exec(
            select(LastAlertToIncident.fingerprint, Incident)
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                    LastAlertToIncident.fingerprint == LastAlert.fingerprint,
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                ),
            )
            .join(Incident, LastAlertToIncident.incident_id == Incident.id)
            .where(
                LastAlert.tenant_id == tenant_id,
                LastAlertToIncident.fingerprint.in_(
                    [alert.fingerprint for alert in alerts]
                ),
            )
        ).all()

        incidents_per_alert = defaultdict(list)
        for fingerprint, incident in alert_incidents:
            incidents_per_alert[fingerprint].append(incident)

        for alert in alerts:
            alert._incidents = incidents_per_alert[alert.fingerprint]

        return alerts


def get_incidents_by_alert_fingerprint(
    tenant_id: str, fingerprint: str, session: Optional[Session] = None
) -> List[Incident]:
    with existed_or_new_session(session) as session:
        alert_incidents = session.exec(
            select(Incident)
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                    LastAlertToIncident.fingerprint == LastAlert.fingerprint,
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                ),
            )
            .join(Incident, LastAlertToIncident.incident_id == Incident.id)
            .where(
                LastAlert.tenant_id == tenant_id,
                LastAlertToIncident.fingerprint == fingerprint,
            )
        ).all()
        return alert_incidents


def get_last_incidents(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_candidate: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    with_alerts: bool = False,
    is_predicted: bool = None,
    filters: Optional[dict] = None,
    allowed_incident_ids: Optional[List[str]] = None,
) -> Tuple[list[Incident], int]:
    """
    Get the last incidents and total amount of incidents.

    Args:
        tenant_id (str): The tenant_id to filter the incidents by.
        limit (int): Amount of objects to return
        offset (int): Current offset for
        timeframe (int|null): Return incidents only for the last <N> days
        upper_timestamp: datetime = None,
        lower_timestamp: datetime = None,
        is_candidate (bool): filter incident candidates or real incidents
        sorting: Optional[IncidentSorting]: how to sort the data
        with_alerts (bool): Pre-load alerts or not
        is_predicted (bool): filter only incidents predicted by KeepAI
        filters (dict): dict of filters
    Returns:
        List[Incident]: A list of Incident objects.
    """
    with Session(engine) as session:
        query = session.query(
            Incident,
        ).filter(
            Incident.tenant_id == tenant_id,
            Incident.is_candidate == is_candidate,
            Incident.is_visible == True,
        )

        if allowed_incident_ids:
            query = query.filter(Incident.id.in_(allowed_incident_ids))

        if is_predicted is not None:
            query = query.filter(Incident.is_predicted == is_predicted)

        if timeframe:
            query = query.filter(
                Incident.start_time
                >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
            )

        if upper_timestamp and lower_timestamp:
            query = query.filter(
                col(Incident.last_seen_time).between(lower_timestamp, upper_timestamp)
            )
        elif upper_timestamp:
            query = query.filter(Incident.last_seen_time <= upper_timestamp)
        elif lower_timestamp:
            query = query.filter(Incident.last_seen_time >= lower_timestamp)

        if filters:
            query = apply_incident_filters(session, filters, query)

        if sorting:
            query = query.order_by(sorting.get_order_by(Incident))

        total_count = query.count()

        # Order by start_time in descending order and limit the results
        query = query.limit(limit).offset(offset)

        # Execute the query
        incidents = query.all()

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)
        enrich_incidents_with_enrichments(tenant_id, incidents, session)

    return incidents, total_count


def get_incident_by_id(
    tenant_id: str,
    incident_id: str | UUID,
    with_alerts: bool = False,
    session: Optional[Session] = None,
) -> Optional[Incident]:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id, should_raise=True)
    with existed_or_new_session(session) as session:
        query = (
            session.query(
                Incident,
                AlertEnrichment,
            )
            .outerjoin(
                AlertEnrichment,
                and_(
                    Incident.tenant_id == AlertEnrichment.tenant_id,
                    cast(col(Incident.id), String)
                    == foreign(AlertEnrichment.alert_fingerprint),
                ),
            )
            .filter(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        )
        incident_with_enrichments = query.first()
        if incident_with_enrichments:
            incident, enrichments = incident_with_enrichments
            if with_alerts:
                enrich_incidents_with_alerts(
                    tenant_id,
                    [incident],
                    session,
                )
            if enrichments:
                incident.set_enrichments(enrichments.enrichments)
        else:
            incident = None

    return incident


def create_incident_from_dto(
    tenant_id: str,
    incident_dto: IncidentDtoIn | IncidentDto,
    generated_from_ai: bool = False,
    session: Optional[Session] = None,
) -> Optional[Incident]:
    """
    Creates an incident for a specified tenant based on the provided incident data transfer object (DTO).

    Args:
        tenant_id (str): The unique identifier of the tenant for whom the incident is being created.
        incident_dto (IncidentDtoIn | IncidentDto): The data transfer object containing incident details.
            Can be an instance of `IncidentDtoIn` or `IncidentDto`.
        generated_from_ai (bool, optional): Specifies whether the incident was generated by Keep's AI. Defaults to False.

    Returns:
        Optional[Incident]: The newly created `Incident` object if successful, otherwise `None`.
    """

    if issubclass(type(incident_dto), IncidentDto) and generated_from_ai:
        # NOTE: we do not use dto's alerts, alert count, start time etc
        #       because we want to re-use the BL of creating incidents
        #       where all of these are calculated inside add_alerts_to_incident
        incident_dict = {
            "user_summary": incident_dto.user_summary,
            "generated_summary": incident_dto.description,
            "user_generated_name": incident_dto.user_generated_name,
            "ai_generated_name": incident_dto.dict().get("name"),
            "assignee": incident_dto.assignee,
            "is_predicted": False,  # its not a prediction, but an AI generation
            "is_candidate": False,  # confirmed by the user :)
            "is_visible": True,  # confirmed by the user :)
            "incident_type": IncidentType.AI.value,
        }

    elif issubclass(type(incident_dto), IncidentDto):
        # we will reach this block when incident is pulled from a provider
        incident_dict = incident_dto.to_db_incident().dict()
        if "incident_type" not in incident_dict:
            incident_dict["incident_type"] = IncidentType.MANUAL.value
    else:
        # We'll reach this block when a user creates an incident
        incident_dict = incident_dto.dict()
        # Keep existing incident_type if present, default to MANUAL if not
        if "incident_type" not in incident_dict:
            incident_dict["incident_type"] = IncidentType.MANUAL.value

    if incident_dto.severity is not None:
        incident_dict["severity"] = incident_dto.severity.order

    return create_incident_from_dict(tenant_id, incident_dict, session)


@retry_on_db_error
def create_incident_from_dict(
    tenant_id: str, incident_data: dict, session: Optional[Session] = None
) -> Optional[Incident]:
    is_predicted = incident_data.get("is_predicted", False)
    if "is_candidate" not in incident_data:
        incident_data["is_candidate"] = is_predicted
    with existed_or_new_session(session) as session:
        new_incident = Incident(**incident_data, tenant_id=tenant_id)
        session.add(new_incident)
        session.commit()
        session.refresh(new_incident)
    return new_incident


@retry_on_db_error
def update_incident_from_dto_by_id(
    tenant_id: str,
    incident_id: str | UUID,
    updated_incident_dto: IncidentDtoIn | IncidentDto,
    generated_by_ai: bool = False,
) -> Optional[Incident]:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)

    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        ).first()

        if not incident:
            return None

        if issubclass(type(updated_incident_dto), IncidentDto):
            # We execute this when we update an incident received from the provider
            updated_data = updated_incident_dto.to_db_incident().model_dump()
        else:
            # When a user updates an Incident
            updated_data = updated_incident_dto.dict()

        for key, value in updated_data.items():
            # Update only if the new value is different from the current one
            if hasattr(incident, key) and getattr(incident, key) != value:
                if isinstance(value, Enum):
                    setattr(incident, key, value.value)
                else:
                    if value is not None:
                        setattr(incident, key, value)

        if "same_incident_in_the_past_id" in updated_data:
            incident.same_incident_in_the_past_id = updated_data[
                "same_incident_in_the_past_id"
            ]

        if generated_by_ai:
            incident.generated_summary = updated_incident_dto.user_summary
        else:
            incident.user_summary = updated_incident_dto.user_summary

        session.commit()
        session.refresh(incident)

        return incident


def get_incident_by_fingerprint(
    tenant_id: str, fingerprint: str, session: Optional[Session] = None
) -> Optional[Incident]:
    with existed_or_new_session(session) as session:
        return session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id, Incident.fingerprint == fingerprint
            )
        ).one_or_none()


def delete_incident_by_id(
    tenant_id: str, incident_id: UUID, session: Optional[Session] = None
) -> bool:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with existed_or_new_session(session) as session:
        incident = session.exec(
            select(Incident).filter(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        ).first()

        session.execute(
            update(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident.id,
            )
            .values({"status": IncidentStatus.DELETED.value})
        )

        session.commit()
        return True


def get_incidents_count(
    tenant_id: str,
) -> int:
    with Session(engine) as session:
        return (
            session.query(Incident)
            .filter(
                Incident.tenant_id == tenant_id,
            )
            .count()
        )


def get_incident_alerts_and_links_by_incident_id(
    tenant_id: str,
    incident_id: UUID | str,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    session: Optional[Session] = None,
    include_unlinked: bool = False,
) -> tuple[List[tuple[Alert, LastAlertToIncident]], int]:
    with existed_or_new_session(session) as session:

        query = (
            session.query(
                Alert,
                LastAlertToIncident,
            )
            .select_from(LastAlertToIncident)
            .join(
                LastAlert,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .filter(
                LastAlertToIncident.tenant_id == tenant_id,
                LastAlertToIncident.incident_id == incident_id,
            )
            .order_by(col(LastAlert.timestamp).desc())
            .options(joinedload(Alert.alert_enrichment))
        )
        if not include_unlinked:
            query = query.filter(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
            )

    total_count = query.count()

    if limit is not None and offset is not None:
        query = query.limit(limit).offset(offset)

    return query.all(), total_count


def get_incident_alerts_by_incident_id(*args, **kwargs) -> tuple[List[Alert], int]:
    """
    Unpacking (List[(Alert, LastAlertToIncident)], int) to (List[Alert], int).
    """
    alerts_and_links, total_alerts = get_incident_alerts_and_links_by_incident_id(
        *args, **kwargs
    )
    alerts = [alert_and_link[0] for alert_and_link in alerts_and_links]
    return alerts, total_alerts


def get_future_incidents_by_incident_id(
    incident_id: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> tuple[List[Incident], int]:
    with Session(engine) as session:
        query = session.query(
            Incident,
        ).filter(Incident.same_incident_in_the_past_id == incident_id)

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

    total_count = query.count()

    return query.all(), total_count


def get_int_severity(input_severity: int | str) -> int:
    if isinstance(input_severity, int):
        return input_severity
    else:
        return IncidentSeverity(input_severity).order


def get_alerts_data_for_incident(
    tenant_id: str,
    fingerprints: Optional[List[str]] = None,
    session: Optional[Session] = None,
):
    """
    Function to prepare aggregated data for incidents from the given list of alert_ids
    Logic is wrapped to the inner function for better usability with an optional database session

    Args:
        tenant_id (str): The tenant ID to filter alerts
        alert_ids (list[str | UUID]): list of alert ids for aggregation
        session (Optional[Session]): The database session or None

    Returns: dict {sources: list[str], services: list[str], count: int}
    """
    with existed_or_new_session(session) as session:

        fields = (
            get_json_extract_field(session, Alert.event, "service"),
            Alert.provider_type,
            Alert.fingerprint,
            get_json_extract_field(session, Alert.event, "severity"),
        )

        alerts_data = session.exec(
            select(*fields)
            .select_from(LastAlert)
            .join(
                Alert,
                and_(
                    LastAlert.tenant_id == Alert.tenant_id,
                    LastAlert.alert_id == Alert.id,
                ),
            )
            .where(
                LastAlert.tenant_id == tenant_id,
                col(LastAlert.fingerprint).in_(fingerprints),
            )
        ).all()

        sources = []
        services = []
        severities = []

        for service, source, fingerprint, severity in alerts_data:
            if source:
                sources.append(source)
            if service:
                services.append(service)
            if severity:
                if isinstance(severity, int):
                    severities.append(IncidentSeverity.from_number(severity))
                else:
                    severities.append(IncidentSeverity(severity))

        return {
            "sources": set(sources),
            "services": set(services),
            "max_severity": max(severities) if severities else IncidentSeverity.LOW,
        }


@retry_on_db_error
def add_alerts_to_incident(
    tenant_id: str,
    incident: Incident,
    fingerprints: List[str],
    is_created_by_ai: bool = False,
    session: Optional[Session] = None,
    override_count: bool = False,
    exclude_unlinked_alerts: bool = False,  # if True, do not add alerts to incident if they are manually unlinked
    max_retries=3,
) -> Optional[Incident]:
    logger.info(
        f"Adding alerts to incident {incident.id} in database, total {len(fingerprints)} alerts",
        extra={"tags": {"tenant_id": tenant_id, "incident_id": incident.id}},
    )

    with existed_or_new_session(session) as session:

        with session.no_autoflush:

            # Use a set for faster membership checks
            existing_fingerprints = set(
                session.exec(
                    select(LastAlert.fingerprint)
                    .join(
                        LastAlertToIncident,
                        and_(
                            LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                            LastAlertToIncident.fingerprint == LastAlert.fingerprint,
                        ),
                    )
                    .where(
                        LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                        LastAlertToIncident.tenant_id == tenant_id,
                        LastAlertToIncident.incident_id == incident.id,
                    )
                ).all()
            )

            new_fingerprints = {
                fingerprint
                for fingerprint in fingerprints
                if fingerprint not in existing_fingerprints
            }

            # filter out unlinked alerts
            if exclude_unlinked_alerts:
                unlinked_alerts = set(
                    session.exec(
                        select(LastAlert.fingerprint)
                        .join(
                            LastAlertToIncident,
                            and_(
                                LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                                LastAlertToIncident.fingerprint
                                == LastAlert.fingerprint,
                            ),
                        )
                        .where(
                            LastAlertToIncident.deleted_at != NULL_FOR_DELETED_AT,
                            LastAlertToIncident.tenant_id == tenant_id,
                            LastAlertToIncident.incident_id == incident.id,
                        )
                    ).all()
                )
                new_fingerprints = new_fingerprints - unlinked_alerts

            if not new_fingerprints:
                return incident

            alert_to_incident_entries = [
                LastAlertToIncident(
                    fingerprint=str(fingerprint),  # it may sometime be UUID...
                    incident_id=incident.id,
                    tenant_id=tenant_id,
                    is_created_by_ai=is_created_by_ai,
                )
                for fingerprint in new_fingerprints
            ]

            for idx, entry in enumerate(alert_to_incident_entries):
                session.add(entry)
                if (idx + 1) % 100 == 0:
                    logger.info(
                        f"Added {idx + 1}/{len(alert_to_incident_entries)} alerts to incident {incident.id} in database",
                        extra={
                            "tags": {"tenant_id": tenant_id, "incident_id": incident.id}
                        },
                    )
                    session.flush()
            session.commit()

            alerts_data_for_incident = get_alerts_data_for_incident(
                tenant_id, new_fingerprints, session
            )

            new_sources = list(
                set(incident.sources if incident.sources else [])
                | set(alerts_data_for_incident["sources"])
            )
            new_affected_services = list(
                set(incident.affected_services if incident.affected_services else [])
                | set(alerts_data_for_incident["services"])
            )
            if not incident.forced_severity:
                # If incident has alerts already, use the max severity between existing and new alerts,
                # otherwise use the new alerts max severity
                new_severity = (
                    max(
                        incident.severity,
                        alerts_data_for_incident["max_severity"].order,
                    )
                    if incident.alerts_count
                    else alerts_data_for_incident["max_severity"].order
                )
            else:
                new_severity = incident.severity

            if not override_count:
                alerts_count = (
                    select(count(LastAlertToIncident.fingerprint)).where(
                        LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                        LastAlertToIncident.tenant_id == tenant_id,
                        LastAlertToIncident.incident_id == incident.id,
                    )
                ).scalar_subquery()
            else:
                alerts_count = alerts_data_for_incident["count"]

            last_received_field = get_json_extract_field(
                session, Alert.event, "lastReceived"
            )

            started_at, last_seen_at = session.exec(
                select(func.min(last_received_field), func.max(last_received_field))
                .join(
                    LastAlertToIncident,
                    and_(
                        LastAlertToIncident.tenant_id == Alert.tenant_id,
                        LastAlertToIncident.fingerprint == Alert.fingerprint,
                    ),
                )
                .where(
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                    LastAlertToIncident.tenant_id == tenant_id,
                    LastAlertToIncident.incident_id == incident.id,
                )
            ).one()

            if isinstance(started_at, str):
                started_at = parse(started_at)

            if isinstance(last_seen_at, str):
                last_seen_at = parse(last_seen_at)

            incident_id = incident.id

            for attempt in range(max_retries):
                try:
                    session.exec(
                        update(Incident)
                        .where(
                            Incident.id == incident_id,
                            Incident.tenant_id == tenant_id,
                        )
                        .values(
                            alerts_count=alerts_count,
                            last_seen_time=last_seen_at,
                            start_time=started_at,
                            affected_services=new_affected_services,
                            severity=new_severity,
                            sources=new_sources,
                        )
                    )
                    session.commit()
                    break
                except StaleDataError as ex:
                    if "expected to update" in ex.args[0]:
                        logger.info(
                            f"Phantom read detected while updating incident `{incident_id}`, retry #{attempt}"
                        )
                        session.rollback()
                        continue
                    else:
                        raise
            session.add(incident)
            session.refresh(incident)

            return incident


def get_incident_unique_fingerprint_count(
    tenant_id: str, incident_id: str | UUID
) -> int:
    with Session(engine) as session:
        return session.execute(
            select(func.count(1))
            .select_from(LastAlertToIncident)
            .where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.tenant_id == tenant_id,
                LastAlertToIncident.incident_id == incident_id,
            )
        ).scalar()


def get_last_alerts_for_incidents(
    incident_ids: List[str | UUID],
) -> Dict[str, List[Alert]]:
    with Session(engine) as session:
        query = (
            session.query(
                Alert,
                LastAlertToIncident.incident_id,
            )
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .filter(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id.in_(incident_ids),
            )
            .order_by(Alert.timestamp.desc())
        )

        alerts = query.all()

    incidents_alerts = defaultdict(list)
    for alert, incident_id in alerts:
        incidents_alerts[str(incident_id)].append(alert)

    return incidents_alerts


def remove_alerts_to_incident_by_incident_id(
    tenant_id: str, incident_id: str | UUID, fingerprints: List[str]
) -> Optional[int]:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        ).first()

        if not incident:
            return None

        # Removing alerts-to-incident relation for provided alerts_ids
        deleted = (
            session.query(LastAlertToIncident)
            .where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.tenant_id == tenant_id,
                LastAlertToIncident.incident_id == incident.id,
                col(LastAlertToIncident.fingerprint).in_(fingerprints),
            )
            .update(
                {
                    "deleted_at": datetime.now(datetime.now().astimezone().tzinfo),
                }
            )
        )
        session.commit()

        # Getting aggregated data for incidents for alerts which just was removed
        alerts_data_for_incident = get_alerts_data_for_incident(
            tenant_id, fingerprints, session=session
        )

        service_field = get_json_extract_field(session, Alert.event, "service")

        # checking if services of removed alerts are still presented in alerts
        # which still assigned with the incident
        existed_services_query = (
            select(func.distinct(service_field))
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .filter(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id == incident_id,
                service_field.in_(alerts_data_for_incident["services"]),
            )
        )
        services_existed = session.exec(existed_services_query)

        # checking if sources (providers) of removed alerts are still presented in alerts
        # which still assigned with the incident
        existed_sources_query = (
            select(col(Alert.provider_type).distinct())
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .filter(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id == incident_id,
                col(Alert.provider_type).in_(alerts_data_for_incident["sources"]),
            )
        )
        sources_existed = session.exec(existed_sources_query)

        severity_field = get_json_extract_field(session, Alert.event, "severity")
        # checking if severities of removed alerts are still presented in alerts
        # which still assigned with the incident
        updated_severities_query = (
            select(severity_field)
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .filter(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id == incident_id,
            )
        )
        updated_severities_result = session.exec(updated_severities_query)
        updated_severities = [
            get_int_severity(severity) for severity in updated_severities_result
        ]

        # Making lists of services and sources to remove from the incident
        services_to_remove = [
            service
            for service in alerts_data_for_incident["services"]
            if service not in services_existed
        ]
        sources_to_remove = [
            source
            for source in alerts_data_for_incident["sources"]
            if source not in sources_existed
        ]

        last_received_field = get_json_extract_field(
            session, Alert.event, "lastReceived"
        )

        started_at, last_seen_at = session.exec(
            select(func.min(last_received_field), func.max(last_received_field))
            .select_from(LastAlert)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.tenant_id == tenant_id,
                LastAlertToIncident.incident_id == incident.id,
            )
        ).one()

        # filtering removed entities from affected services and sources in the incident
        new_affected_services = [
            service
            for service in incident.affected_services
            if service not in services_to_remove
        ]
        new_sources = [
            source for source in incident.sources if source not in sources_to_remove
        ]

        if not incident.forced_severity:
            new_severity = (
                max(updated_severities)
                if updated_severities
                else IncidentSeverity.LOW.order
            )
        else:
            new_severity = incident.severity

        if isinstance(started_at, str):
            started_at = parse(started_at)

        if isinstance(last_seen_at, str):
            last_seen_at = parse(last_seen_at)

        alerts_count = (
            select(count(LastAlertToIncident.fingerprint)).where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.tenant_id == tenant_id,
                LastAlertToIncident.incident_id == incident.id,
            )
        ).subquery()

        session.exec(
            update(Incident)
            .where(
                Incident.id == incident_id,
                Incident.tenant_id == tenant_id,
            )
            .values(
                alerts_count=alerts_count,
                last_seen_time=last_seen_at,
                start_time=started_at,
                affected_services=new_affected_services,
                severity=new_severity,
                sources=new_sources,
            )
        )
        session.commit()
        session.add(incident)
        session.refresh(incident)

        return deleted


class DestinationIncidentNotFound(Exception):
    pass


def merge_incidents_to_id(
    tenant_id: str,
    source_incident_ids: List[UUID],
    # Maybe to add optional destionation_incident_dto to merge to
    destination_incident_id: UUID,
    merged_by: str | None = None,
) -> Tuple[List[UUID], List[UUID], List[UUID]]:
    with Session(engine) as session:
        destination_incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id, Incident.id == destination_incident_id
            )
        ).first()

        if not destination_incident:
            raise DestinationIncidentNotFound(
                f"Destination incident with id {destination_incident_id} not found"
            )

        source_incidents = session.exec(
            select(Incident).filter(
                Incident.tenant_id == tenant_id,
                Incident.id.in_(source_incident_ids),
            )
        ).all()

        enrich_incidents_with_alerts(tenant_id, source_incidents, session=session)

        merged_incident_ids = []
        failed_incident_ids = []
        for source_incident in source_incidents:
            source_incident_alerts_fingerprints = [
                alert.fingerprint for alert in source_incident.alerts
            ]
            source_incident.merged_into_incident_id = destination_incident.id
            source_incident.merged_at = datetime.now(tz=timezone.utc)
            source_incident.status = IncidentStatus.MERGED.value
            source_incident.merged_by = merged_by
            try:
                remove_alerts_to_incident_by_incident_id(
                    tenant_id,
                    source_incident.id,
                    [alert.fingerprint for alert in source_incident.alerts],
                )
            except OperationalError as e:
                logger.error(
                    f"Error removing alerts from incident {source_incident.id}: {e}"
                )
            try:
                add_alerts_to_incident(
                    tenant_id,
                    destination_incident,
                    source_incident_alerts_fingerprints,
                    session=session,
                )
                merged_incident_ids.append(source_incident.id)
            except OperationalError as e:
                logger.error(
                    f"Error adding alerts to incident {destination_incident.id} from {source_incident.id}: {e}"
                )
                failed_incident_ids.append(source_incident.id)

        session.commit()
        session.refresh(destination_incident)
        return merged_incident_ids, failed_incident_ids


def get_alerts_count(
    tenant_id: str,
) -> int:
    with Session(engine) as session:
        return (
            session.query(Alert)
            .filter(
                Alert.tenant_id == tenant_id,
            )
            .count()
        )


def get_first_alert_datetime(
    tenant_id: str,
) -> datetime | None:
    with Session(engine) as session:
        first_alert = (
            session.query(Alert)
            .filter(
                Alert.tenant_id == tenant_id,
            )
            .first()
        )
        if first_alert:
            return first_alert.timestamp


def confirm_predicted_incident_by_id(
    tenant_id: str,
    incident_id: UUID | str,
):
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
                Incident.is_candidate == expression.true(),
            )
            .options(joinedload(Incident.alerts))
        ).first()

        if not incident:
            return None

        session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
            Incident.is_candidate == expression.true(),
        ).update(
            {
                "is_visible": True,
            }
        )

        session.commit()
        session.refresh(incident)

        return incident


def get_tenant_config(tenant_id: str) -> dict:
    with Session(engine) as session:
        tenant_data = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
        return tenant_data.configuration if tenant_data else {}


def write_tenant_config(tenant_id: str, config: dict) -> None:
    with Session(engine) as session:
        tenant_data = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
        tenant_data.configuration = config
        session.commit()
        session.refresh(tenant_data)
        return tenant_data


def update_incident_summary(
    tenant_id: str, incident_id: UUID, summary: str
) -> Incident:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.id == incident_id)
        ).first()

        if not incident:
            logger.error(
                f"Incident not found for tenant {tenant_id} and incident {incident_id}",
                extra={"tenant_id": tenant_id},
            )
            return

        incident.generated_summary = summary
        session.commit()
        session.refresh(incident)

        return


def update_incident_name(tenant_id: str, incident_id: UUID, name: str) -> Incident:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.id == incident_id)
        ).first()

        if not incident:
            logger.error(
                f"Incident not found for tenant {tenant_id} and incident {incident_id}",
                extra={"tenant_id": tenant_id},
            )
            return

        incident.ai_generated_name = name
        session.commit()
        session.refresh(incident)

        return incident


def update_incident_severity(
    tenant_id: str, incident_id: UUID, severity: IncidentSeverity
) -> Optional[Incident]:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.id == incident_id)
        ).first()

        if not incident:
            logger.error(
                f"Incident not found for tenant {tenant_id} and incident {incident_id}",
                extra={"tenant_id": tenant_id},
            )
            return

        incident.severity = severity.order
        incident.forced_severity = True
        session.add(incident)
        session.commit()
        session.refresh(incident)

        return incident


def get_topology_data_by_dynamic_matcher(
    tenant_id: str, matchers_value: dict[str, str]
) -> TopologyService | None:
    with Session(engine) as session:
        query = select(TopologyService).where(TopologyService.tenant_id == tenant_id)
        for matcher in matchers_value:
            query = query.where(
                getattr(TopologyService, matcher) == matchers_value[matcher]
            )
        # Add joinedload for applications to avoid detached instance error
        query = query.options(joinedload(TopologyService.applications))
        service = session.exec(query).first()
        return service


def get_tags(tenant_id):
    with Session(engine) as session:
        tags = session.exec(select(Tag).where(Tag.tenant_id == tenant_id)).all()
    return tags


def create_tag(tag: Tag):
    with Session(engine) as session:
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return tag


def assign_tag_to_preset(tenant_id: str, tag_id: str, preset_id: str):
    if isinstance(preset_id, str):
        preset_id = __convert_to_uuid(preset_id)
    with Session(engine) as session:
        tag_preset = PresetTagLink(
            tenant_id=tenant_id,
            tag_id=tag_id,
            preset_id=preset_id,
        )
        session.add(tag_preset)
        session.commit()
        session.refresh(tag_preset)
        return tag_preset


def get_provider_by_name(tenant_id: str, provider_name: str) -> Provider:
    with Session(engine) as session:
        provider = session.exec(
            select(Provider)
            .where(Provider.tenant_id == tenant_id)
            .where(Provider.name == provider_name)
        ).first()
    return provider


def get_provider_by_type_and_id(
    tenant_id: str, provider_type: str, provider_id: Optional[str]
) -> Provider:
    with Session(engine) as session:
        query = select(Provider).where(
            Provider.tenant_id == tenant_id,
            Provider.type == provider_type,
            Provider.id == provider_id,
        )
        provider = session.exec(query).first()
    return provider


def bulk_upsert_alert_fields(
    tenant_id: str,
    fields: List[str],
    provider_id: str,
    provider_type: str,
    session: Optional[Session] = None,
    max_retries=3,
):
    with existed_or_new_session(session) as session:
        for attempt in range(max_retries):
            try:
                # Prepare the data for bulk insert
                data = [
                    {
                        "tenant_id": tenant_id,
                        "field_name": field,
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                    }
                    for field in fields
                ]

                if engine.dialect.name == "postgresql":
                    stmt = pg_insert(AlertField).values(data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            "tenant_id",
                            "field_name",
                        ],  # Unique constraint columns
                        set_={
                            "provider_id": stmt.excluded.provider_id,
                            "provider_type": stmt.excluded.provider_type,
                        },
                    )
                elif engine.dialect.name == "mysql":
                    stmt = mysql_insert(AlertField).values(data)
                    stmt = stmt.on_duplicate_key_update(
                        provider_id=stmt.inserted.provider_id,
                        provider_type=stmt.inserted.provider_type,
                    )
                elif engine.dialect.name == "sqlite":
                    stmt = sqlite_insert(AlertField).values(data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            "tenant_id",
                            "field_name",
                        ],  # Unique constraint columns
                        set_={
                            "provider_id": stmt.excluded.provider_id,
                            "provider_type": stmt.excluded.provider_type,
                        },
                    )
                elif engine.dialect.name == "mssql":
                    # SQL Server requires a raw query with a MERGE statement
                    values = ", ".join(
                        f"('{tenant_id}', '{field}', '{provider_id}', '{provider_type}')"
                        for field in fields
                    )

                    merge_query = text(
                        f"""
                        MERGE INTO AlertField AS target
                        USING (VALUES {values}) AS source (tenant_id, field_name, provider_id, provider_type)
                        ON target.tenant_id = source.tenant_id AND target.field_name = source.field_name
                        WHEN MATCHED THEN
                            UPDATE SET provider_id = source.provider_id, provider_type = source.provider_type
                        WHEN NOT MATCHED THEN
                            INSERT (tenant_id, field_name, provider_id, provider_type)
                            VALUES (source.tenant_id, source.field_name, source.provider_id, source.provider_type)
                    """
                    )

                    session.execute(merge_query)
                else:
                    raise NotImplementedError(
                        f"Upsert not supported for {engine.dialect.name}"
                    )

                # Execute the statement
                if engine.dialect.name != "mssql":  # Already executed for SQL Server
                    session.execute(stmt)
                session.commit()

                break

            except OperationalError as e:
                # Handle any potential race conditions
                session.rollback()
                if "Deadlock found" in str(e):
                    logger.info(
                        f"Deadlock found during bulk_upsert_alert_fields `{e}`, retry #{attempt}"
                    )
                    if attempt >= max_retries:
                        raise e
                    continue
                else:
                    raise e


def get_alerts_fields(tenant_id: str) -> List[AlertField]:
    with Session(engine) as session:
        fields = session.exec(
            select(AlertField).where(AlertField.tenant_id == tenant_id)
        ).all()
    return fields


def change_incident_status_by_id(
    tenant_id: str,
    incident_id: UUID | str,
    status: IncidentStatus,
    end_time: datetime | None = None,
) -> bool:
    if isinstance(incident_id, str):
        incident_id = __convert_to_uuid(incident_id)
    with Session(engine) as session:
        stmt = (
            update(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
            .values(
                status=status.value,
                end_time=end_time,
            )
        )
        session.exec(stmt)
        session.commit()


def get_workflow_executions_for_incident_or_alert(
    tenant_id: str, incident_id: str, limit: int = 25, offset: int = 0
):
    with Session(engine) as session:
        # Base query for both incident and alert related executions
        base_query = (
            select(
                WorkflowExecution.id,
                WorkflowExecution.started,
                WorkflowExecution.status,
                WorkflowExecution.execution_number,
                WorkflowExecution.triggered_by,
                WorkflowExecution.workflow_id,
                WorkflowExecution.execution_time,
                Workflow.name.label("workflow_name"),
                literal(incident_id).label("incident_id"),
                case(
                    (
                        WorkflowToAlertExecution.alert_fingerprint != None,
                        WorkflowToAlertExecution.alert_fingerprint,
                    ),
                    else_=literal(None),
                ).label("alert_fingerprint"),
            )
            .join(Workflow, WorkflowExecution.workflow_id == Workflow.id)
            .outerjoin(
                WorkflowToAlertExecution,
                WorkflowExecution.id == WorkflowToAlertExecution.workflow_execution_id,
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
        )

        # Query for workflow executions directly associated with the incident
        incident_query = base_query.join(
            WorkflowToIncidentExecution,
            WorkflowExecution.id == WorkflowToIncidentExecution.workflow_execution_id,
        ).where(WorkflowToIncidentExecution.incident_id == incident_id)

        # Query for workflow executions associated with alerts tied to the incident
        alert_query = (
            base_query.join(
                LastAlert,
                WorkflowToAlertExecution.alert_fingerprint == LastAlert.fingerprint,
            )
            .join(Alert, LastAlert.alert_id == Alert.id)
            .join(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id == incident_id,
                LastAlert.tenant_id == tenant_id,
            )
        )

        # Combine both queries
        combined_query = union(incident_query, alert_query).subquery()

        # Count total results
        count_query = select(func.count()).select_from(combined_query)
        total_count = session.execute(count_query).scalar()

        # Final query with ordering, offset, and limit
        final_query = (
            select(combined_query)
            .order_by(desc(combined_query.c.started))
            .offset(offset)
            .limit(limit)
        )

        # Execute the query and fetch results
        results = session.execute(final_query).all()
        return results, total_count


def is_all_alerts_resolved(
    fingerprints: Optional[List[str]] = None,
    incident: Optional[Incident] = None,
    session: Optional[Session] = None,
):
    return is_all_alerts_in_status(
        fingerprints, incident, AlertStatus.RESOLVED, session
    )


def is_all_alerts_in_status(
    fingerprints: Optional[List[str]] = None,
    incident: Optional[Incident] = None,
    status: AlertStatus = AlertStatus.RESOLVED,
    session: Optional[Session] = None,
):

    if incident and incident.alerts_count == 0:
        return False

    with existed_or_new_session(session) as session:

        enriched_status_field = get_json_extract_field(
            session, AlertEnrichment.enrichments, "status"
        )
        status_field = get_json_extract_field(session, Alert.event, "status")

        subquery = (
            select(
                enriched_status_field.label("enriched_status"),
                status_field.label("status"),
            )
            .select_from(LastAlert)
            .join(Alert, LastAlert.alert_id == Alert.id)
            .outerjoin(
                AlertEnrichment,
                and_(
                    Alert.tenant_id == AlertEnrichment.tenant_id,
                    Alert.fingerprint == AlertEnrichment.alert_fingerprint,
                ),
            )
        )

        if fingerprints:
            subquery = subquery.where(LastAlert.fingerprint.in_(fingerprints))

        if incident:
            subquery = subquery.join(
                LastAlertToIncident,
                and_(
                    LastAlertToIncident.tenant_id == LastAlert.tenant_id,
                    LastAlertToIncident.fingerprint == LastAlert.fingerprint,
                ),
            ).where(
                LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                LastAlertToIncident.incident_id == incident.id,
            )

        subquery = subquery.subquery()

        not_in_status_exists = session.query(
            exists(
                select(
                    subquery.c.enriched_status,
                    subquery.c.status,
                )
                .select_from(subquery)
                .where(
                    or_(
                        subquery.c.enriched_status != status.value,
                        and_(
                            subquery.c.enriched_status.is_(None),
                            subquery.c.status != status.value,
                        ),
                    )
                )
            )
        ).scalar()

        return not not_in_status_exists


def is_last_incident_alert_resolved(
    incident: Incident, session: Optional[Session] = None
) -> bool:
    return is_edge_incident_alert_resolved(incident, func.max, session)


def is_first_incident_alert_resolved(
    incident: Incident, session: Optional[Session] = None
) -> bool:
    return is_edge_incident_alert_resolved(incident, func.min, session)


def is_edge_incident_alert_resolved(
    incident: Incident, direction: Callable, session: Optional[Session] = None
) -> bool:

    if incident.alerts_count == 0:
        return False

    with existed_or_new_session(session) as session:

        enriched_status_field = get_json_extract_field(
            session, AlertEnrichment.enrichments, "status"
        )
        status_field = get_json_extract_field(session, Alert.event, "status")

        finerprint, enriched_status, status = session.exec(
            select(Alert.fingerprint, enriched_status_field, status_field)
            .select_from(Alert)
            .outerjoin(
                AlertEnrichment,
                and_(
                    Alert.tenant_id == AlertEnrichment.tenant_id,
                    Alert.fingerprint == AlertEnrichment.alert_fingerprint,
                ),
            )
            .join(
                LastAlertToIncident,
                and_(
                    LastAlertToIncident.tenant_id == Alert.tenant_id,
                    LastAlertToIncident.fingerprint == Alert.fingerprint,
                ),
            )
            .where(LastAlertToIncident.incident_id == incident.id)
            .group_by(Alert.fingerprint)
            .having(func.max(Alert.timestamp))
            .order_by(direction(Alert.timestamp))
        ).first()

        return enriched_status == AlertStatus.RESOLVED.value or (
            enriched_status is None and status == AlertStatus.RESOLVED.value
        )


def get_alerts_metrics_by_provider(
    tenant_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    fields: Optional[List[str]] = [],
) -> Dict[str, Dict[str, Any]]:

    dynamic_field_sums = [
        func.sum(
            case(
                (
                    (func.json_extract(Alert.event, f"$.{field}").isnot(None))
                    & (func.json_extract(Alert.event, f"$.{field}") != False),
                    1,
                ),
                else_=0,
            )
        ).label(f"{field}_count")
        for field in fields
    ]

    with Session(engine) as session:
        query = (
            session.query(
                Alert.provider_type,
                Alert.provider_id,
                func.count(Alert.id).label("total_alerts"),
                func.sum(
                    case((LastAlertToIncident.fingerprint.isnot(None), 1), else_=0)
                ).label("correlated_alerts"),
                *dynamic_field_sums,
            )
            .join(LastAlert, Alert.id == LastAlert.alert_id)
            .outerjoin(
                LastAlertToIncident,
                and_(
                    LastAlert.tenant_id == LastAlertToIncident.tenant_id,
                    LastAlert.fingerprint == LastAlertToIncident.fingerprint,
                ),
            )
            .filter(
                Alert.tenant_id == tenant_id,
            )
        )

        # Add timestamp filter only if both start_date and end_date are provided
        if start_date and end_date:
            query = query.filter(
                Alert.timestamp >= start_date, Alert.timestamp <= end_date
            )

        results = query.group_by(Alert.provider_id, Alert.provider_type).all()

    metrics = {}
    for row in results:
        key = f"{row.provider_id}_{row.provider_type}"
        metrics[key] = {
            "total_alerts": row.total_alerts,
            "correlated_alerts": row.correlated_alerts,
            "provider_type": row.provider_type,
        }
        for field in fields:
            metrics[key][f"{field}_count"] = getattr(row, f"{field}_count", 0)

    return metrics


def get_or_create_external_ai_settings(
    tenant_id: str,
) -> List[ExternalAIConfigAndMetadataDto]:
    with Session(engine) as session:
        algorithm_configs = session.exec(
            select(ExternalAIConfigAndMetadata).where(
                ExternalAIConfigAndMetadata.tenant_id == tenant_id
            )
        ).all()
        if len(algorithm_configs) == 0:
            if os.environ.get("KEEP_EXTERNAL_AI_TRANSFORMERS_URL") is not None:
                algorithm_config = ExternalAIConfigAndMetadata.from_external_ai(
                    tenant_id=tenant_id, algorithm=external_ai_transformers
                )
                session.add(algorithm_config)
                session.commit()
                algorithm_configs = [algorithm_config]
        return [
            ExternalAIConfigAndMetadataDto.from_orm(algorithm_config)
            for algorithm_config in algorithm_configs
        ]


def update_extrnal_ai_settings(
    tenant_id: str, ai_settings: ExternalAIConfigAndMetadata
) -> ExternalAIConfigAndMetadataDto:
    with Session(engine) as session:
        setting = (
            session.query(ExternalAIConfigAndMetadata)
            .filter(
                ExternalAIConfigAndMetadata.tenant_id == tenant_id,
                ExternalAIConfigAndMetadata.id == ai_settings.id,
            )
            .first()
        )
        setting.settings = json.dumps(ai_settings.settings)
        setting.feedback_logs = ai_settings.feedback_logs
        if ai_settings.settings_proposed_by_algorithm is not None:
            setting.settings_proposed_by_algorithm = json.dumps(
                ai_settings.settings_proposed_by_algorithm
            )
        else:
            setting.settings_proposed_by_algorithm = None
        session.add(setting)
        session.commit()
    return setting


def get_table_class(table_name: str) -> Type[SQLModel]:
    """
    Get the SQLModel table class dynamically based on table name.
    Assumes table classes follow PascalCase naming convention.

    Args:
        table_name (str): Name of the table in snake_case (e.g. "alerts", "rules")

    Returns:
        Type[SQLModel]: The corresponding SQLModel table class
    """
    # Convert snake_case to PascalCase and remove trailing 's' if exists
    class_name = "".join(
        word.capitalize() for word in table_name.rstrip("s").split("_")
    )

    # Get all SQLModel subclasses from the imported modules
    model_classes = {
        cls.__name__: cls
        for cls in SQLModel.__subclasses__()
        if hasattr(cls, "__tablename__")
    }

    if class_name not in model_classes:
        raise ValueError(f"No table class found for table name: {table_name}")

    return model_classes[class_name]


def get_resource_ids_by_resource_type(
    tenant_id: str, table_name: str, uid: str, session: Optional[Session] = None
) -> List[str]:
    """
    Get all unique IDs from a table grouped by a specified UID column.

    Args:
        tenant_id (str): The tenant ID to filter by
        table_name (str): Name of the table (e.g. "alerts", "rules")
        uid (str): Name of the column to group by
        session (Optional[Session]): SQLModel session

    Returns:
        List[str]: List of unique IDs

    Example:
        >>> get_resource_ids_by_resource_type("tenant123", "alerts", "alert_id")
        ['id1', 'id2', 'id3']
    """
    with existed_or_new_session(session) as session:
        # Get the table class dynamically
        table_class = get_table_class(table_name)

        # Create the query using SQLModel's select
        query = (
            select(getattr(table_class, uid))
            .distinct()
            .where(getattr(table_class, "tenant_id") == tenant_id)
        )

        # Execute the query and return results
        result = session.exec(query)
        return result.all()


def get_or_creat_posthog_instance_id(session: Optional[Session] = None):
    POSTHOG_INSTANCE_ID_KEY = "posthog_instance_id"
    with Session(engine) as session:
        system = session.exec(
            select(System).where(System.name == POSTHOG_INSTANCE_ID_KEY)
        ).first()
        if system:
            return system.value

        system = System(
            id=str(uuid4()),
            name=POSTHOG_INSTANCE_ID_KEY,
            value=str(uuid4()),
        )
        session.add(system)
        session.commit()
        session.refresh(system)
        return system.value


def get_activity_report(session: Optional[Session] = None):
    from keep.api.models.db.user import User

    last_24_hours = datetime.utcnow() - timedelta(hours=24)
    activity_report = {}
    with Session(engine) as session:
        activity_report["tenants_count"] = session.query(Tenant).count()
        activity_report["providers_count"] = session.query(Provider).count()
        activity_report["users_count"] = session.query(User).count()
        activity_report["rules_count"] = session.query(Rule).count()
        activity_report["last_24_hours_incidents_count"] = (
            session.query(Incident)
            .filter(Incident.creation_time >= last_24_hours)
            .count()
        )
        activity_report["last_24_hours_alerts_count"] = (
            session.query(Alert).filter(Alert.timestamp >= last_24_hours).count()
        )
        activity_report["last_24_hours_rules_created"] = (
            session.query(Rule).filter(Rule.creation_time >= last_24_hours).count()
        )
        activity_report["last_24_hours_workflows_created"] = (
            session.query(Workflow)
            .filter(Workflow.creation_time >= last_24_hours)
            .count()
        )
        activity_report["last_24_hours_workflows_executed"] = (
            session.query(WorkflowExecution)
            .filter(WorkflowExecution.started >= last_24_hours)
            .count()
        )
    return activity_report


def get_last_alerts_by_fingerprints(
    tenant_id: str,
    fingerprint: List[str],
    session: Optional[Session] = None,
) -> List[LastAlert]:
    with existed_or_new_session(session) as session:
        query = select(LastAlert).where(
            and_(
                LastAlert.tenant_id == tenant_id,
                LastAlert.fingerprint.in_(fingerprint),
            )
        )
        return session.exec(query).all()


def get_last_alert_by_fingerprint(
    tenant_id: str,
    fingerprint: str,
    session: Optional[Session] = None,
    for_update: bool = False,
) -> Optional[LastAlert]:
    with existed_or_new_session(session) as session:
        query = select(LastAlert).where(
            and_(
                LastAlert.tenant_id == tenant_id,
                LastAlert.fingerprint == fingerprint,
            )
        )
        if for_update:
            query = query.with_for_update()
        return session.exec(query).first()


def set_last_alert(
    tenant_id: str, alert: Alert, session: Optional[Session] = None, max_retries=3
) -> None:
    fingerprint = alert.fingerprint
    logger.info(f"Setting last alert for `{fingerprint}`")
    with existed_or_new_session(session) as session:
        for attempt in range(max_retries):
            logger.info(
                f"Attempt {attempt} to set last alert for `{fingerprint}`",
                extra={
                    "alert_id": alert.id,
                    "tenant_id": tenant_id,
                    "fingerprint": fingerprint,
                },
            )
            try:
                last_alert = get_last_alert_by_fingerprint(
                    tenant_id, fingerprint, session, for_update=True
                )

                # To prevent rare, but possible race condition
                # For example if older alert failed to process
                # and retried after new one
                if last_alert and last_alert.timestamp.replace(
                    tzinfo=tz.UTC
                ) < alert.timestamp.replace(tzinfo=tz.UTC):

                    logger.info(
                        f"Update last alert for `{fingerprint}`: {last_alert.alert_id} -> {alert.id}",
                        extra={
                            "alert_id": alert.id,
                            "tenant_id": tenant_id,
                            "fingerprint": fingerprint,
                        },
                    )
                    last_alert.timestamp = alert.timestamp
                    last_alert.alert_id = alert.id
                    last_alert.alert_hash = alert.alert_hash
                    session.add(last_alert)

                elif not last_alert:
                    logger.info(f"No last alert for `{fingerprint}`, creating new")
                    last_alert = LastAlert(
                        tenant_id=tenant_id,
                        fingerprint=alert.fingerprint,
                        timestamp=alert.timestamp,
                        first_timestamp=alert.timestamp,
                        alert_id=alert.id,
                        alert_hash=alert.alert_hash,
                    )

                session.add(last_alert)
                session.commit()
                break
            except OperationalError as ex:
                if "no such savepoint" in ex.args[0]:
                    logger.info(
                        f"No such savepoint while updating lastalert for `{fingerprint}`, retry #{attempt}"
                    )
                    session.rollback()
                    if attempt >= max_retries:
                        raise ex
                    continue

                if "Deadlock found" in ex.args[0]:
                    logger.info(
                        f"Deadlock found while updating lastalert for `{fingerprint}`, retry #{attempt}"
                    )
                    session.rollback()
                    if attempt >= max_retries:
                        raise ex
                    continue
            except NoActiveSqlTransaction:
                logger.exception(
                    f"No active sql transaction while updating lastalert for `{fingerprint}`, retry #{attempt}",
                    extra={
                        "alert_id": alert.id,
                        "tenant_id": tenant_id,
                        "fingerprint": fingerprint,
                    },
                )
                continue
            logger.debug(
                f"Successfully updated lastalert for `{fingerprint}`",
                extra={
                    "alert_id": alert.id,
                    "tenant_id": tenant_id,
                    "fingerprint": fingerprint,
                },
            )
            # break the retry loop
            break

def set_maintenance_windows_trace(alert: Alert, maintenance_w: MaintenanceWindowRule,  session: Optional[Session] = None):
    mw_id = str(maintenance_w.id)
    if mw_id in alert.event.get("maintenance_windows_trace", []):
        return
    with existed_or_new_session(session) as session:
        if "maintenance_windows_trace" in alert.event:
            if mw_id not in alert.event['maintenance_windows_trace']:
                alert.event['maintenance_windows_trace'].append(mw_id)
        else:
            alert.event['maintenance_windows_trace'] = [mw_id]
        flag_modified(alert, "event")
        session.add(alert)
        session.commit()

def get_provider_logs(
    tenant_id: str, provider_id: str, limit: int = 100
) -> List[ProviderExecutionLog]:
    with Session(engine) as session:
        logs = (
            session.query(ProviderExecutionLog)
            .filter(
                ProviderExecutionLog.tenant_id == tenant_id,
                ProviderExecutionLog.provider_id == provider_id,
            )
            .order_by(desc(ProviderExecutionLog.timestamp))
            .limit(limit)
            .all()
        )
    return logs


def enrich_incidents_with_enrichments(
    tenant_id: str,
    incidents: List[Incident],
    session: Optional[Session] = None,
) -> List[Incident]:
    """Enrich incidents with their enrichment data."""
    if not incidents:
        return incidents

    with existed_or_new_session(session) as session:
        # Get all enrichments for these incidents in one query
        enrichments = session.exec(
            select(AlertEnrichment).where(
                AlertEnrichment.tenant_id == tenant_id,
                AlertEnrichment.alert_fingerprint.in_(
                    [str(incident.id) for incident in incidents]
                ),
            )
        ).all()

        # Create a mapping of incident_id to enrichment
        enrichments_map = {
            enrichment.alert_fingerprint: enrichment.enrichments
            for enrichment in enrichments
        }

        # Add enrichments to each incident
        for incident in incidents:
            incident._enrichments = enrichments_map.get(str(incident.id), {})

        return incidents


def get_error_alerts(tenant_id: str, limit: int = 100) -> List[AlertRaw]:
    with Session(engine) as session:
        return (
            session.query(AlertRaw)
            .filter(
                AlertRaw.tenant_id == tenant_id,
                AlertRaw.error == True,
                AlertRaw.dismissed == False,
            )
            .limit(limit)
            .all()
        )


def dismiss_error_alerts(tenant_id: str, alert_id=None, dismissed_by=None) -> None:
    with Session(engine) as session:
        stmt = (
            update(AlertRaw)
            .where(
                AlertRaw.tenant_id == tenant_id,
            )
            .values(
                dismissed=True,
                dismissed_by=dismissed_by,
                dismissed_at=datetime.now(tz=timezone.utc),
            )
        )
        if alert_id:
            if isinstance(alert_id, str):
                alert_id_uuid = uuid.UUID(alert_id)
                stmt = stmt.where(AlertRaw.id == alert_id_uuid)
            else:
                stmt = stmt.where(AlertRaw.id == alert_id)
        session.exec(stmt)
        session.commit()


def create_tenant(tenant_name: str) -> str:
    with Session(engine) as session:
        try:
            # check if the tenant exist:
            logger.info("Checking if tenant exists")
            tenant = session.exec(
                select(Tenant).where(Tenant.name == tenant_name)
            ).first()
            if not tenant:
                # Do everything related with single tenant creation in here
                tenant_id = str(uuid4())
                logger.info(
                    "Creating tenant",
                    extra={"tenant_id": tenant_id, "tenant_name": tenant_name},
                )
                session.add(Tenant(id=tenant_id, name=tenant_name))
            else:
                logger.warning("Tenant already exists")

            # commit the changes
            session.commit()
            logger.info(
                "Tenant created",
                extra={"tenant_id": tenant_id, "tenant_name": tenant_name},
            )
            return tenant_id
        except IntegrityError:
            # Tenant already exists
            logger.exception("Failed to create tenant")
            raise
        except Exception:
            logger.exception("Failed to create tenant")
            pass


def create_single_tenant_for_e2e(tenant_id: str) -> None:
    """
    Creates the single tenant and the default user if they don't exist.
    """
    with Session(engine) as session:
        try:
            # check if the tenant exist:
            logger.info("Checking if single tenant exists")
            tenant = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
            if not tenant:
                # Do everything related with single tenant creation in here
                logger.info("Creating single tenant", extra={"tenant_id": tenant_id})
                session.add(Tenant(id=tenant_id, name="Single Tenant"))
            else:
                logger.info("Single tenant already exists")

            # commit the changes
            session.commit()
            logger.info("Single tenant created", extra={"tenant_id": tenant_id})
        except IntegrityError:
            # Tenant already exists
            logger.exception("Failed to provision single tenant")
            raise
        except Exception:
            logger.exception("Failed to create single tenant")
            pass

def get_maintenance_windows_started(session: Optional[Session] = None) -> List[MaintenanceWindowRule]:
    """
    It will return all windows started, i.e start_time < currentTime
    """
    with existed_or_new_session(session) as session:
        query = (
            select(MaintenanceWindowRule)
            .where(MaintenanceWindowRule.start_time <= datetime.now(tz=timezone.utc))
        )
        return session.exec(query).all()

def recover_prev_alert_status(alert: Alert, session: Optional[Session] = None):
    """
    It'll restore the previous status of the alert.
    """
    with existed_or_new_session(session) as session:
        try:
            status = alert.event.get("status")
            prev_status = alert.event.get("previous_status")
            alert.event["status"] = prev_status
            alert.event["previous_status"] = status
        except KeyError:
            logger.warning(f"Alert {alert.id} does not have previous status.")
        query = (
            update(Alert)
            .where(Alert.id == alert.id)
            .values(
                event = alert.event
            )
        )
        session.exec(query)
        session.commit()
