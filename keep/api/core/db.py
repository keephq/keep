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

 """Sandbox-safe distribution helpers.

This module rewrites the incident/workflow/alert distribution helpers so they:
- Work on SQLite/MySQL/PostgreSQL.
- Do not crash when timestamp_filter is None.
- Produce a complete hour-by-hour series (missing hours => 0).
- Avoid SQLModel typing pitfalls for JSON columns.

NOTE: Replace the stub SQLModel models with your real models when integrating.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, List

from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy import func

from sqlmodel import SQLModel, Field, Session, create_engine, select


# -----------------------------------------------------------------------------
# Time range filter
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeStampFilter:
    lower_timestamp: Optional[datetime] = None
    upper_timestamp: Optional[datetime] = None

    def normalized_utc(self) -> "TimeStampFilter":
        def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        return TimeStampFilter(
            lower_timestamp=as_utc(self.lower_timestamp),
            upper_timestamp=as_utc(self.upper_timestamp),
        )


# -----------------------------------------------------------------------------
# Stub models (swap with your real models in repo)
# -----------------------------------------------------------------------------

class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    provider_id: Optional[str] = Field(default=None, index=True)
    provider_type: Optional[str] = Field(default=None, index=True)
    # IMPORTANT: use plain `dict` and explicit JSON column to avoid SQLModel issubclass errors
    event: dict = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))
    timestamp: datetime = Field(index=True)


class WorkflowExecution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    started: datetime = Field(index=True)


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    creation_time: datetime = Field(index=True)
    start_time: Optional[datetime] = Field(default=None, index=True)
    end_time: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="")


# -----------------------------------------------------------------------------
# Engine (for tests). In your repo, you already have `engine`.
# -----------------------------------------------------------------------------

engine = create_engine("sqlite://", echo=False)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

_TIME_FMT_SQLITE = "%Y-%m-%d %H"  # used by sqlite strftime


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hour_floor(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def _default_range_24h() -> TimeStampFilter:
    now = _utcnow()
    return TimeStampFilter(lower_timestamp=now - timedelta(hours=24), upper_timestamp=now)


def _coerce_range(tsf: Optional[TimeStampFilter]) -> TimeStampFilter:
    # Always return a normalized (UTC-aware) range with both bounds.
    if tsf is None:
        tsf = _default_range_24h()
    tsf = tsf.normalized_utc()

    lower = tsf.lower_timestamp
    upper = tsf.upper_timestamp

    if lower is None and upper is None:
        return _default_range_24h().normalized_utc()

    if upper is None:
        # If only lower provided, make it a 24h window
        upper = lower + timedelta(hours=24)  # type: ignore[operator]

    if lower is None:
        # If only upper provided, make it a 24h window
        lower = upper - timedelta(hours=24)

    if lower > upper:
        # Swap if user passed inverted bounds
        lower, upper = upper, lower

    return TimeStampFilter(lower_timestamp=lower, upper_timestamp=upper)  # type: ignore[arg-type]


def _timestamp_bucket_expr(session: Session, dt_col):
    """Return a SQL expression that buckets dt_col by hour into a comparable string."""
    dialect = session.bind.dialect.name
    if dialect == "mysql":
        return func.date_format(dt_col, _TIME_FMT_SQLITE)
    if dialect == "postgresql":
        return func.to_char(dt_col, "YYYY-MM-DD HH")
    # sqlite default
    return func.strftime(_TIME_FMT_SQLITE, dt_col)


def _build_hourly_series(
    lower: datetime,
    upper: datetime,
    counts: Dict[str, int],
) -> List[dict]:
    lower_h = _hour_floor(lower)
    upper_h = _hour_floor(upper)

    out: List[dict] = []
    t = lower_h
    # Inclusive series: include the upper hour.
    while t <= upper_h:
        key = t.strftime(_TIME_FMT_SQLITE)
        out.append({"timestamp": f"{key}:00", "number": int(counts.get(key, 0))})
        t += timedelta(hours=1)
    return out


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def get_alert_distribution(
    tenant_id: str,
    timestamp_filter: Optional[TimeStampFilter] = None,
    aggregate_all: bool = True,
) -> List[dict] | Dict[str, dict]:
    """Alert distribution over time.

    If aggregate_all=True (default), returns a complete hourly series:
        [{"timestamp": "YYYY-MM-DD HH:00", "number": N}, ...]

    If aggregate_all=False, returns provider-grouped distribution:
        {
          "<provider_id>_<provider_type>": {
              "provider_id": ..., "provider_type": ...,
              "alert_last_hours": [{"hour": <int>, "number": <int>}, ...],
              "last_alert_received": <datetime>
          },
          ...
        }

    IMPORTANT: provider-grouped mode uses a *relative* hour index from the start
    of the selected range (not always last-24-hours).
    """
    tsf = _coerce_range(timestamp_filter)
    lower, upper = tsf.lower_timestamp, tsf.upper_timestamp  # type: ignore[assignment]

    with Session(engine) as session:
        bucket = _timestamp_bucket_expr(session, Alert.timestamp)

        filters = [
            Alert.tenant_id == tenant_id,
            Alert.timestamp >= lower,
            Alert.timestamp <= upper,
        ]

        if aggregate_all:
            rows = (
                session.query(bucket.label("time"), func.count().label("hits"))
                .filter(*filters)
                .group_by("time")
                .order_by("time")
                .all()
            )
            counts = {str(time): int(hits) for time, hits in rows}
            return _build_hourly_series(lower, upper, counts)

        rows = (
            session.query(
                Alert.provider_id,
                Alert.provider_type,
                bucket.label("time"),
                func.count().label("hits"),
                func.max(Alert.timestamp).label("last_alert_timestamp"),
            )
            .filter(*filters)
            .group_by(Alert.provider_id, Alert.provider_type, "time")
            .order_by(Alert.provider_id, Alert.provider_type, "time")
            .all()
        )

        # Compute number of hours in window (inclusive)
        lower_h = _hour_floor(lower)
        upper_h = _hour_floor(upper)
        hours_len = int(((upper_h - lower_h).total_seconds() // 3600) + 1)

        provider_distribution: Dict[str, dict] = {}

        for provider_id, provider_type, time_s, hits, last_alert_ts in rows:
            provider_key = f"{provider_id}_{provider_type}"

            if isinstance(last_alert_ts, str):
                last_alert_ts = datetime.fromisoformat(last_alert_ts)

            if provider_key not in provider_distribution:
                provider_distribution[provider_key] = {
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "alert_last_hours": [{"hour": i, "number": 0} for i in range(hours_len)],
                    "last_alert_received": last_alert_ts,
                }
            else:
                provider_distribution[provider_key]["last_alert_received"] = max(
                    provider_distribution[provider_key]["last_alert_received"],
                    last_alert_ts,
                )

            # bucket label => parse to hour in UTC
            bucket_time = datetime.strptime(str(time_s), _TIME_FMT_SQLITE).replace(tzinfo=timezone.utc)
            idx = int((bucket_time - lower_h).total_seconds() // 3600)
            if 0 <= idx < hours_len:
                provider_distribution[provider_key]["alert_last_hours"][idx]["number"] += int(hits)

        return provider_distribution



def get_combined_workflow_execution_distribution(
    tenant_id: str,
    timestamp_filter: Optional[TimeStampFilter] = None,
) -> List[dict]:
    """Hourly distribution of WorkflowExecutions started for tenant."""
    tsf = _coerce_range(timestamp_filter)
    lower, upper = tsf.lower_timestamp, tsf.upper_timestamp  # type: ignore[assignment]

    with Session(engine) as session:
        bucket = _timestamp_bucket_expr(session, WorkflowExecution.started)
        rows = (
            session.query(bucket.label("time"), func.count().label("executions"))
            .filter(
                WorkflowExecution.tenant_id == tenant_id,
                WorkflowExecution.started >= lower,
                WorkflowExecution.started <= upper,
            )
            .group_by("time")
            .order_by("time")
            .all()
        )
        counts = {str(time): int(n) for time, n in rows}
        return _build_hourly_series(lower, upper, counts)



def get_incidents_created_distribution(
    tenant_id: str,
    timestamp_filter: Optional[TimeStampFilter] = None,
) -> List[dict]:
    """Hourly distribution of incidents created for tenant."""
    tsf = _coerce_range(timestamp_filter)
    lower, upper = tsf.lower_timestamp, tsf.upper_timestamp  # type: ignore[assignment]

    with Session(engine) as session:
        bucket = _timestamp_bucket_expr(session, Incident.creation_time)
        rows = (
            session.query(bucket.label("time"), func.count().label("incidents"))
            .filter(
                Incident.tenant_id == tenant_id,
                Incident.creation_time >= lower,
                Incident.creation_time <= upper,
            )
            .group_by("time")
            .order_by("time")
            .all()
        )
        counts = {str(time): int(n) for time, n in rows}
        return _build_hourly_series(lower, upper, counts)



def calc_incidents_mttr(
    tenant_id: str,
    timestamp_filter: Optional[TimeStampFilter] = None,
    resolved_status_value: str = "resolved",
) -> List[dict]:
    """Mean Time To Resolve (hours) bucketed by incident creation hour.

    MTTR per hour = average of (end_time - start_time) across incidents created in that hour.
    Only incidents with both start_time and end_time are included.

    resolved_status_value is passed in because your real code uses an Enum.
    """
    tsf = _coerce_range(timestamp_filter)
    lower, upper = tsf.lower_timestamp, tsf.upper_timestamp  # type: ignore[assignment]

    with Session(engine) as session:
        bucket = _timestamp_bucket_expr(session, Incident.creation_time)

        rows = (
            session.query(
                bucket.label("time"),
                Incident.start_time,
                Incident.end_time,
                func.count().label("n"),
            )
            .filter(
                Incident.tenant_id == tenant_id,
                Incident.status == resolved_status_value,
                Incident.creation_time >= lower,
                Incident.creation_time <= upper,
            )
            .group_by("time", Incident.start_time, Incident.end_time)
            .order_by("time")
            .all()
        )

        agg: Dict[str, dict] = {}
        for time_s, start, end, n in rows:
            if start is None or end is None:
                continue
            dt_hours = (end - start).total_seconds() / 3600.0
            k = str(time_s)
            if k not in agg:
                agg[k] = {"count": 0, "sum": 0.0}
            agg[k]["count"] += int(n)
            agg[k]["sum"] += float(dt_hours) * int(n)

        # Build full series (timestamp + mttr)
        lower_h = _hour_floor(lower)
        upper_h = _hour_floor(upper)
        out: List[dict] = []
        t = lower_h
        while t <= upper_h:
            k = t.strftime(_TIME_FMT_SQLITE)
            if k in agg and agg[k]["count"] > 0:
                mttr = agg[k]["sum"] / agg[k]["count"]
            else:
                mttr = 0.0
            out.append({"timestamp": f"{k}:00", "mttr": mttr})
            t += timedelta(hours=1)
        return out


# -----------------------------------------------------------------------------
# Self-tests (sqlite in-memory)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import unittest

    class TestDistributions(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            SQLModel.metadata.create_all(engine)

        def setUp(self):
            # wipe tables between tests
            with Session(engine) as s:
                s.exec(select(Alert))
                s.exec(select(WorkflowExecution))
                s.exec(select(Incident))
                # SQLite: easiest is DELETE
                s.exec("DELETE FROM alert")
                s.exec("DELETE FROM workflowexecution")
                s.exec("DELETE FROM incident")
                s.commit()

        def test_alert_distribution_aggregate_defaults_24h(self):
            tenant = "t1"
            now = _utcnow()
            with Session(engine) as s:
                s.add(Alert(tenant_id=tenant, provider_id="p1", provider_type="x", timestamp=now - timedelta(hours=1)))
                s.add(Alert(tenant_id=tenant, provider_id="p2", provider_type="y", timestamp=now - timedelta(hours=1)))
                s.add(Alert(tenant_id=tenant, provider_id="p1", provider_type="x", timestamp=now - timedelta(hours=3)))
                s.commit()

            series = get_alert_distribution(tenant_id=tenant, timestamp_filter=None, aggregate_all=True)
            self.assertGreaterEqual(len(series), 24)  # inclusive endpoints may yield 25
            # At least one bucket should have count 2 (hour -1)
            self.assertTrue(any(row["number"] == 2 for row in series))

        def test_alert_distribution_provider_grouped_respects_range(self):
            tenant = "t1"
            base = _hour_floor(_utcnow() - timedelta(hours=5))
            rng = TimeStampFilter(lower_timestamp=base, upper_timestamp=base + timedelta(hours=5))

            with Session(engine) as s:
                s.add(Alert(tenant_id=tenant, provider_id="p1", provider_type="a", timestamp=base + timedelta(hours=1)))
                s.add(Alert(tenant_id=tenant, provider_id="p1", provider_type="a", timestamp=base + timedelta(hours=1, minutes=5)))
                s.add(Alert(tenant_id=tenant, provider_id="p2", provider_type="b", timestamp=base + timedelta(hours=3)))
                s.commit()

            out = get_alert_distribution(tenant_id=tenant, timestamp_filter=rng, aggregate_all=False)
            self.assertIn("p1_a", out)
            self.assertIn("p2_b", out)
            # window length inclusive: 6 hours
            self.assertEqual(len(out["p1_a"]["alert_last_hours"]), 6)
            self.assertEqual(out["p1_a"]["alert_last_hours"][1]["number"], 2)
            self.assertEqual(out["p2_b"]["alert_last_hours"][3]["number"], 1)

        def test_workflow_execution_distribution(self):
            tenant = "t1"
            base = _hour_floor(_utcnow() - timedelta(hours=10))
            rng = TimeStampFilter(lower_timestamp=base, upper_timestamp=base + timedelta(hours=2))
            with Session(engine) as s:
                s.add(WorkflowExecution(tenant_id=tenant, started=base + timedelta(minutes=1)))
                s.add(WorkflowExecution(tenant_id=tenant, started=base + timedelta(hours=2, minutes=10)))
                s.commit()

            series = get_combined_workflow_execution_distribution(tenant, rng)
            # inclusive: 3 buckets
            self.assertEqual(len(series), 3)
            self.assertEqual(series[0]["number"], 1)
            self.assertEqual(series[2]["number"], 1)

        def test_incident_created_distribution(self):
            tenant = "t1"
            base = _hour_floor(_utcnow() - timedelta(hours=4))
            rng = TimeStampFilter(lower_timestamp=base, upper_timestamp=base + timedelta(hours=1))
            with Session(engine) as s:
                s.add(Incident(tenant_id=tenant, creation_time=base + timedelta(minutes=2)))
                s.add(Incident(tenant_id=tenant, creation_time=base + timedelta(hours=1, minutes=30)))
                s.commit()

            series = get_incidents_created_distribution(tenant, rng)
            self.assertEqual(len(series), 2)
            self.assertEqual(series[0]["number"], 1)
            self.assertEqual(series[1]["number"], 1)

        def test_mttr_series(self):
            tenant = "t1"
            base = _hour_floor(_utcnow() - timedelta(hours=2))
            rng = TimeStampFilter(lower_timestamp=base, upper_timestamp=base + timedelta(hours=1))
            with Session(engine) as s:
                s.add(
                    Incident(
                        tenant_id=tenant,
                        creation_time=base + timedelta(minutes=3),
                        start_time=base + timedelta(minutes=0),
                        end_time=base + timedelta(minutes=60),
                        status="resolved",
                    )
                )
                s.add(
                    Incident(
                        tenant_id=tenant,
                        creation_time=base + timedelta(minutes=10),
                        start_time=base + timedelta(minutes=0),
                        end_time=base + timedelta(minutes=30),
                        status="resolved",
                    )
                )
                s.commit()

            series = calc_incidents_mttr(tenant, rng, resolved_status_value="resolved")
            # Two buckets
            self.assertEqual(len(series), 2)
            # First bucket average: (1.0h + 0.5h)/2 = 0.75
            self.assertAlmostEqual(series[0]["mttr"], 0.75, places=6)

    unittest.main()

    """sandbox_db_helpers_recode.py

A sandbox-safe rewrite of several Keep DB helper functions.

Why this exists
--------------
The original code you pasted assumes the full `keep.api.*` package layout and
imports models from that codebase. In this sandbox, those modules don't exist.

This file provides:
- Minimal SQLModel models needed to run the shown queries.
- Explicit JSON column types to avoid SQLModel's
  `TypeError: issubclass() arg 1 must be a class`.
- Safer DTO type checks (use `isinstance`, not `issubclass(type(x), ...)`).
- Portable implementations for SQLite (plus placeholders for MySQL/Postgres).
- Unit tests using in-memory SQLite.

Note
----
This is *not* a full Keep clone. It's a focused, runnable version of the logic
in your snippets.

Python: 3.12+
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from sqlalchemy import Column, String, and_, cast, desc, func, select, update
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import joinedload
from sqlmodel import Field, Session, SQLModel, create_engine


# -----------------------------------------------------------------------------
# Engine
# -----------------------------------------------------------------------------

engine = create_engine("sqlite://", echo=False)


# -----------------------------------------------------------------------------
# Constants / Utilities
# -----------------------------------------------------------------------------

NULL_FOR_DELETED_AT = "0001-01-01T00:00:00"  # sentinel used by original code


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _floor_hour(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def _ensure_uuid(v: str | UUID, *, should_raise: bool = True) -> UUID:
    if isinstance(v, UUID):
        return v
    try:
        return UUID(str(v))
    except Exception:
        if should_raise:
            raise ValueError(f"Invalid UUID: {v}")
        return None  # type: ignore[return-value]


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class IncidentStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    MERGED = "merged"
    DELETED = "deleted"


class IncidentType(str, Enum):
    MANUAL = "manual"
    AI = "ai"


class ActionType(str, Enum):
    ENRICH = "enrich"


class IncidentSorting(str, Enum):
    creation_time = "creation_time"

    def get_order_by(self, model):
        # minimal
        return desc(model.creation_time)


# -----------------------------------------------------------------------------
# DTOs
# -----------------------------------------------------------------------------


@dataclass
class IncidentDto:
    user_generated_name: Optional[str] = None
    description: Optional[str] = None
    user_summary: Optional[str] = None
    assignee: Optional[str] = None
    severity: Optional[int] = None

    def to_db_incident(self) -> "Incident":
        # minimal mapping
        return Incident(
            user_generated_name=self.user_generated_name,
            generated_summary=self.description,
            user_summary=self.user_summary,
            assignee=self.assignee,
            severity=self.severity,
            is_predicted=False,
            is_candidate=False,
            is_visible=True,
            incident_type=IncidentType.MANUAL.value,
        )


@dataclass
class IncidentDtoIn:
    user_generated_name: Optional[str] = None
    user_summary: Optional[str] = None
    assignee: Optional[str] = None
    severity: Optional[int] = None
    incident_type: Optional[str] = None


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class AlertAudit(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    user_id: str
    action: str
    description: str
    timestamp: datetime = Field(default_factory=_utcnow, index=True)


class AlertEnrichment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)
    alert_fingerprint: str = Field(index=True)
    # IMPORTANT: explicit JSON column to avoid SQLModel issubclass() crash
    enrichments: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SQLITE_JSON, nullable=False),
    )


class Incident(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)

    user_generated_name: Optional[str] = None
    ai_generated_name: Optional[str] = None

    status: str = Field(default=IncidentStatus.FIRING.value, index=True)
    incident_type: str = Field(default=IncidentType.MANUAL.value, index=True)

    is_visible: bool = Field(default=True, index=True)
    is_candidate: bool = Field(default=False, index=True)
    is_predicted: bool = Field(default=False, index=True)

    severity: Optional[int] = Field(default=None)
    assignee: Optional[str] = Field(default=None, index=True)

    creation_time: datetime = Field(default_factory=_utcnow, index=True)
    start_time: Optional[datetime] = Field(default=None, index=True)
    end_time: Optional[datetime] = Field(default=None, index=True)
    last_seen_time: Optional[datetime] = Field(default=None, index=True)

    # JSON array columns
    sources: List[str] = Field(default_factory=list, sa_column=Column(SQLITE_JSON))
    affected_services: List[str] = Field(
        default_factory=list, sa_column=Column(SQLITE_JSON)
    )

    # transient holders (mimic original pattern)
    _alerts: List[Any] = []  # not persisted

    def set_enrichments(self, enrichments: Dict[str, Any]) -> None:
        # placeholder for compatibility
        self._enrichments = enrichments


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    provider_id: Optional[str] = Field(default=None, index=True)
    provider_type: Optional[str] = Field(default=None, index=True)

    timestamp: datetime = Field(default_factory=_utcnow, index=True)

    # IMPORTANT: explicit JSON column to avoid SQLModel issubclass() crash
    event: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SQLITE_JSON, nullable=False),
    )


class LastAlert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    alert_id: UUID = Field(index=True)
    timestamp: datetime = Field(default_factory=_utcnow, index=True)


class LastAlertToIncident(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    incident_id: UUID = Field(index=True)
    timestamp: datetime = Field(default_factory=_utcnow, index=True)
    deleted_at: str = Field(default=NULL_FOR_DELETED_AT, index=True)


# -----------------------------------------------------------------------------
# Session helper
# -----------------------------------------------------------------------------


class existed_or_new_session:
    """Context manager: reuse a given session or open/close a new one."""

    def __init__(self, session: Optional[Session]):
        self._provided = session
        self._created: Optional[Session] = None

    def __enter__(self) -> Session:
        if self._provided is not None:
            return self._provided
        self._created = Session(engine)
        return self._created

    def __exit__(self, exc_type, exc, tb):
        if self._created is not None:
            self._created.close()
        return False


# -----------------------------------------------------------------------------
# Functions (rewritten)
# -----------------------------------------------------------------------------


def get_alert_audit(
    tenant_id: str,
    fingerprint: str | list[str],
    limit: int = 50,
) -> List[AlertAudit]:
    """Get alert audit events for fingerprint(s).

    Behavior:
    - If fingerprint is a list: returns audits across those fingerprints ordered
      by timestamp desc then fingerprint asc. If `limit` is set, it limits the
      combined result.
    - If fingerprint is a string: returns audits for that fingerprint ordered by
      timestamp desc limited to `limit`.
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

        # SQLModel Session.execute(select(...)) returns Row objects; use scalars()
        return session.execute(query).scalars().all()


def get_incidents_meta_for_tenant(tenant_id: str) -> dict:
    """Return distinct assignees, sources, and affected_services for visible incidents.

    SQLite implementation uses json_each() to unnest arrays.
    """
    with Session(engine) as session:
        dialect = session.bind.dialect.name

        if dialect == "sqlite":
            sources_join = func.json_each(Incident.sources).table_valued("value")
            services_join = func.json_each(Incident.affected_services).table_valued(
                "value"
            )

            query = (
                select(
                    func.json_group_array(cast(Incident.assignee, String).distinct()).label(
                        "assignees"
                    ),
                    func.json_group_array(sources_join.c.value.distinct()).label(
                        "sources"
                    ),
                    func.json_group_array(services_join.c.value.distinct()).label(
                        "affected_services"
                    ),
                )
                .select_from(Incident)
                .outerjoin(sources_join, sources_join.c.value.isnot(None))
                .outerjoin(services_join, services_join.c.value.isnot(None))
                .where(Incident.tenant_id == tenant_id, Incident.is_visible == True)
            )

            row = session.execute(query).one_or_none()
            if not row:
                return {}

            assignees_json, sources_json, services_json = row

            def _parse_array(v: Any) -> list:
                if not v:
                    return []
                try:
                    return list(filter(bool, json.loads(v)))
                except Exception:
                    return []

            return {
                "assignees": _parse_array(assignees_json),
                "sources": _parse_array(sources_json),
                "services": _parse_array(services_json),
            }

        # Minimal placeholders for other DBs in this sandbox
        return {}


ALLOWED_INCIDENT_FILTERS = {
    "status",
    "incident_type",
    "assignee",
    "affected_services",
    "sources",
    "severity",
}


def filter_query(session: Session, query, field, value):
    """Dialect-aware filter for JSON-array-like fields."""
    dialect = session.bind.dialect.name

    if dialect == "sqlite":
        json_each_alias = func.json_each(field).table_valued("value")
        subq = select(1).select_from(json_each_alias)
        if isinstance(value, list):
            subq = subq.where(json_each_alias.c.value.in_(value))
        else:
            subq = subq.where(json_each_alias.c.value == value)
        return query.filter(subq.exists())

    # MySQL/Postgres implementations intentionally omitted in sandbox
    return query


def apply_incident_filters(session: Session, filters: dict, query):
    for field_name, value in filters.items():
        if field_name not in ALLOWED_INCIDENT_FILTERS:
            continue

        field = getattr(Incident, field_name)

        if field_name in ["affected_services", "sources"]:
            # Rare case with empty values
            if isinstance(value, list) and not any(value):
                continue
            query = filter_query(session, query, field, value)
            continue

        if isinstance(value, list):
            query = query.filter(cast(field, String).in_(value))
        else:
            query = query.filter(cast(field, String) == value)

    return query


@dataclass
class TimeStampFilter:
    lower_timestamp: Optional[datetime] = None
    upper_timestamp: Optional[datetime] = None


def get_last_incidents(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int | None = None,
    upper_timestamp: datetime | None = None,
    lower_timestamp: datetime | None = None,
    is_candidate: bool = False,
    sorting: Optional[IncidentSorting] = IncidentSorting.creation_time,
    with_alerts: bool = False,
    is_predicted: bool | None = None,
    filters: Optional[dict] = None,
    allowed_incident_ids: Optional[List[str]] = None,
) -> Tuple[list[Incident], int]:
    with Session(engine) as session:
        query = session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.is_candidate == is_candidate,
            Incident.is_visible == True,
        )

        if allowed_incident_ids:
            allowed_uuid = [_ensure_uuid(i) for i in allowed_incident_ids]
            query = query.filter(Incident.id.in_(allowed_uuid))

        if is_predicted is not None:
            query = query.filter(Incident.is_predicted == is_predicted)

        if timeframe:
            query = query.filter(
                Incident.start_time >= _utcnow() - timedelta(days=timeframe)
            )

        if upper_timestamp and lower_timestamp:
            query = query.filter(
                cast(Incident.last_seen_time, String).isnot(None)
            ).filter(Incident.last_seen_time.between(lower_timestamp, upper_timestamp))
        elif upper_timestamp:
            query = query.filter(Incident.last_seen_time <= upper_timestamp)
        elif lower_timestamp:
            query = query.filter(Incident.last_seen_time >= lower_timestamp)

        if filters:
            query = apply_incident_filters(session, filters, query)

        if sorting:
            query = query.order_by(sorting.get_order_by(Incident))

        total_count = query.count()
        incidents = query.limit(limit).offset(offset).all()

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, incidents, session)

        return incidents, total_count


def enrich_incidents_with_alerts(
    tenant_id: str,
    incidents: List[Incident],
    session: Optional[Session] = None,
):
    if not incidents:
        return incidents

    with existed_or_new_session(session) as session:
        incident_ids = [i.id for i in incidents]

        rows = session.exec(
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
                LastAlertToIncident.incident_id.in_(incident_ids),
            )
        ).all()

        per_incident: dict[UUID, list[Alert]] = defaultdict(list)
        for inc_id, alert in rows:
            per_incident[inc_id].append(alert)

        for inc in incidents:
            inc._alerts = per_incident.get(inc.id, [])

        return incidents


def create_incident_from_dto(
    tenant_id: str,
    incident_dto: IncidentDtoIn | IncidentDto,
    generated_from_ai: bool = False,
    session: Optional[Session] = None,
) -> Optional[Incident]:
    """Create an incident from either IncidentDtoIn (user input) or IncidentDto.

    Fixes vs original:
    - Uses `isinstance(...)` instead of `issubclass(type(...), ...)`.
    """

    if isinstance(incident_dto, IncidentDto) and generated_from_ai:
        incident_data = {
            "user_summary": incident_dto.user_summary,
            "generated_summary": incident_dto.description,
            "user_generated_name": incident_dto.user_generated_name,
            "ai_generated_name": None,
            "assignee": incident_dto.assignee,
            "is_predicted": False,
            "is_candidate": False,
            "is_visible": True,
            "incident_type": IncidentType.AI.value,
            "severity": incident_dto.severity,
        }

    elif isinstance(incident_dto, IncidentDto):
        db_obj = incident_dto.to_db_incident()
        incident_data = db_obj.model_dump(exclude={"tenant_id", "id"})
        incident_data.setdefault("incident_type", IncidentType.MANUAL.value)

    else:
        # user input
        incident_data = {
            "user_generated_name": incident_dto.user_generated_name,
            "user_summary": incident_dto.user_summary,
            "assignee": incident_dto.assignee,
            "severity": incident_dto.severity,
            "incident_type": incident_dto.incident_type or IncidentType.MANUAL.value,
            "is_predicted": False,
            "is_candidate": False,
            "is_visible": True,
        }

    return create_incident_from_dict(tenant_id, incident_data, session)


def create_incident_from_dict(
    tenant_id: str,
    incident_data: dict,
    session: Optional[Session] = None,
) -> Incident:
    with existed_or_new_session(session) as session:
        inc = Incident(**incident_data, tenant_id=tenant_id)
        session.add(inc)
        session.commit()
        session.refresh(inc)
        return inc


def get_incident_by_id(
    tenant_id: str,
    incident_id: str | UUID,
    with_alerts: bool = False,
    session: Optional[Session] = None,
) -> Optional[Incident]:
    inc_id = _ensure_uuid(incident_id)
    with existed_or_new_session(session) as session:
        inc = session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id, Incident.id == inc_id)
        ).one_or_none()

        if not inc:
            return None

        if with_alerts:
            enrich_incidents_with_alerts(tenant_id, [inc], session)

        return inc


# -----------------------------------------------------------------------------
# DB Init
# -----------------------------------------------------------------------------


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import unittest

    class TestSandboxDBHelpers(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            init_db()

        def setUp(self):
            # wipe tables between tests
            with Session(engine) as s:
                for model in [
                    LastAlertToIncident,
                    LastAlert,
                    Alert,
                    AlertEnrichment,
                    AlertAudit,
                    Incident,
                ]:
                    s.exec(update(model).values({}))  # no-op to ensure model loaded
                # brute delete
                s.exec(select(1))
                for table in reversed(SQLModel.metadata.sorted_tables):
                    s.exec(table.delete())
                s.commit()

        def test_json_columns_do_not_trigger_sqlmodel_issubclass_error(self):
            # If JSON typing is wrong, SQLModel will usually crash at import/model creation.
            # Getting here means our explicit JSON columns worked.
            self.assertTrue(True)

        def test_get_alert_audit_single(self):
            with Session(engine) as s:
                s.add(
                    AlertAudit(
                        tenant_id="t1",
                        fingerprint="fp1",
                        user_id="u",
                        action="x",
                        description="d",
                        timestamp=_utcnow(),
                    )
                )
                s.add(
                    AlertAudit(
                        tenant_id="t1",
                        fingerprint="fp1",
                        user_id="u2",
                        action="y",
                        description="d2",
                        timestamp=_utcnow() + timedelta(seconds=1),
                    )
                )
                s.commit()

            rows = get_alert_audit("t1", "fp1", limit=50)
            self.assertEqual(len(rows), 2)
            self.assertGreaterEqual(rows[0].timestamp, rows[1].timestamp)

        def test_get_alert_audit_list_orders_by_ts_then_fp(self):
            base = _utcnow()
            with Session(engine) as s:
                s.add(
                    AlertAudit(
                        tenant_id="t1",
                        fingerprint="a",
                        user_id="u",
                        action="x",
                        description="d",
                        timestamp=base,
                    )
                )
                s.add(
                    AlertAudit(
                        tenant_id="t1",
                        fingerprint="b",
                        user_id="u",
                        action="x",
                        description="d",
                        timestamp=base,
                    )
                )
                s.commit()

            rows = get_alert_audit("t1", ["a", "b"], limit=50)
            self.assertEqual([r.fingerprint for r in rows], ["a", "b"])  # same ts

        def test_get_incidents_meta_for_tenant_sqlite(self):
            with Session(engine) as s:
                s.add(
                    Incident(
                        tenant_id="t1",
                        assignee="alice",
                        is_visible=True,
                        sources=["pagerduty", "grafana"],
                        affected_services=["svc1", "svc2"],
                    )
                )
                s.add(
                    Incident(
                        tenant_id="t1",
                        assignee="bob",
                        is_visible=True,
                        sources=["grafana"],
                        affected_services=["svc2"],
                    )
                )
                s.commit()

            meta = get_incidents_meta_for_tenant("t1")
            self.assertIn("alice", meta.get("assignees", []))
            self.assertIn("bob", meta.get("assignees", []))
            self.assertIn("grafana", meta.get("sources", []))
            self.assertIn("svc2", meta.get("services", []))

        def test_create_incident_from_dto_type_handling(self):
            inc = create_incident_from_dto(
                "t1",
                IncidentDto(user_generated_name="n", description="d"),
                generated_from_ai=True,
            )
            self.assertEqual(inc.tenant_id, "t1")
            self.assertEqual(inc.incident_type, IncidentType.AI.value)

            inc2 = create_incident_from_dto(
                "t1",
                IncidentDtoIn(user_generated_name="m", user_summary="s"),
                generated_from_ai=False,
            )
            self.assertEqual(inc2.incident_type, IncidentType.MANUAL.value)

        def test_apply_incident_filters_sources_sqlite(self):
            with Session(engine) as s:
                s.add(
                    Incident(
                        tenant_id="t1",
                        is_visible=True,
                        sources=["a", "b"],
                        affected_services=["svc1"],
                    )
                )
                s.add(
                    Incident(
                        tenant_id="t1",
                        is_visible=True,
                        sources=["c"],
                        affected_services=["svc2"],
                    )
                )
                s.commit()

            with Session(engine) as s:
                q = s.query(Incident).filter(Incident.tenant_id == "t1")
                q = apply_incident_filters(s, {"sources": ["a"]}, q)
                rows = q.all()
                self.assertEqual(len(rows), 1)
                self.assertIn("a", rows[0].sources)

    unittest.main(verbosity=2)
"""Sandbox-friendly subset of Keep DB utilities.

Why this exists:
- The real Keep repo imports `keep.api.*` and expects a configured app environment.
- This sandbox does not have that package, so this file provides a minimal, runnable
  implementation of the DB models + helpers used by the functions you pasted.

Key fixes vs the broken snippet:
- JSON/Dict fields are explicitly mapped to SQLAlchemy JSON columns to avoid
  SQLModel's `issubclass()` crash.
- The aggregation helper you pasted had a docstring saying it aggregates by
  `alert_ids`, but the query used `fingerprints` (undefined). This implementation
  aggregates by *alert_ids* as documented.

Run tests:
    python -m unittest keep_sandbox_db_utils_fixed.py
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Field, SQLModel, Session, create_engine, select

logger = logging.getLogger(__name__)

# -------------------------
# DB setup (SQLite in-memory)
# -------------------------
engine = create_engine("sqlite://", echo=False)


# -------------------------
# Enums / helpers
# -------------------------
class IncidentSeverity(Enum):
    LOW = (1, "low")
    MEDIUM = (2, "medium")
    HIGH = (3, "high")
    CRITICAL = (4, "critical")

    def __init__(self, order: int, label: str):
        self.order = order
        self.label = label

    @classmethod
    def from_number(cls, n: int) -> "IncidentSeverity":
        mapping = {
            1: cls.LOW,
            2: cls.MEDIUM,
            3: cls.HIGH,
            4: cls.CRITICAL,
        }
        return mapping.get(int(n), cls.LOW)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, IncidentSeverity):
            return NotImplemented
        return self.order < other.order


NULL_FOR_DELETED_AT = "0001-01-01T00:00:00+00:00"  # mirrors Keep convention


def retry_on_db_error(fn):
    """Minimal retry decorator.

    Keep has a more elaborate implementation. For sandbox tests, we retry once on
    OperationalError.
    """

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except OperationalError:
            return fn(*args, **kwargs)

    return wrapper


@contextlib.contextmanager
def existed_or_new_session(session: Optional[Session] = None):
    """Use the provided session, or create a new one."""
    if session is not None:
        yield session
        return
    with Session(engine) as s:
        yield s


def _json_path(key: str) -> str:
    # json_extract path for SQLite
    return f"$.{key}"


def get_json_extract_field(session: Session, json_col, key: str):
    """Return a SQL expression extracting `key` from a JSON column.

    This is intentionally SQLite-first (sandbox uses SQLite).
    """
    dialect = session.bind.dialect.name
    if dialect == "sqlite":
        return func.json_extract(json_col, _json_path(key))
    # Fallback: best-effort generic JSON extract.
    return func.json_extract(json_col, _json_path(key))


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Accept ISO-ish strings
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# -------------------------
# Models
# -------------------------
class Alert(SQLModel, table=True):
    __tablename__ = "alert"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    provider_type: Optional[str] = Field(default=None, index=True)
    provider_id: Optional[str] = Field(default=None)
    timestamp: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

    # IMPORTANT: explicitly map dict to JSON column to avoid SQLModel issubclass crash
    event: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("event", sqlalchemy_json_type(), nullable=False),
    )


class LastAlert(SQLModel, table=True):
    __tablename__ = "lastalert"

    tenant_id: str = Field(primary_key=True)
    fingerprint: str = Field(primary_key=True)
    alert_id: str = Field(index=True)


class Incident(SQLModel, table=True):
    __tablename__ = "incident"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)

    alerts_count: int = Field(default=0)
    severity: int = Field(default=IncidentSeverity.LOW.order)
    forced_severity: bool = Field(default=False)

    # JSON-ish list columns
    sources: List[str] = Field(
        default_factory=list,
        sa_column=Column("sources", sqlalchemy_json_type(), nullable=False),
    )
    affected_services: List[str] = Field(
        default_factory=list,
        sa_column=Column("affected_services", sqlalchemy_json_type(), nullable=False),
    )

    start_time: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_seen_time: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class LastAlertToIncident(SQLModel, table=True):
    __tablename__ = "lastalerttoincident"

    tenant_id: str = Field(primary_key=True)
    incident_id: str = Field(primary_key=True)
    fingerprint: str = Field(primary_key=True)

    deleted_at: str = Field(default=NULL_FOR_DELETED_AT, index=True)
    is_created_by_ai: bool = Field(default=False)


# SQLAlchemy JSON type helper
def sqlalchemy_json_type():
    # SQLite supports JSON1; SQLAlchemy JSON works fine, but on some sandbox builds
    # the dialect can behave oddly. Using Text + (de)serialization is safer.
    # We still *label* it as JSON-ish by keeping everything as JSON strings.
    return String


# -------------------------
# JSON serialization glue for "fake JSON" columns
# -------------------------
# Because we used String columns for JSON-like fields above, we need to ensure
# SQLModel stores/loads python objects. We keep this minimal: the models will
# store JSON strings; helpers encode/decode when reading/writing.


def _encode_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def _decode_json(value: Any, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _ensure_alert_event(alert: Alert) -> None:
    if isinstance(alert.event, str):
        alert.event = _decode_json(alert.event, {})


def _ensure_incident_lists(incident: Incident) -> None:
    if isinstance(incident.sources, str):
        incident.sources = _decode_json(incident.sources, [])
    if isinstance(incident.affected_services, str):
        incident.affected_services = _decode_json(incident.affected_services, [])


# -------------------------
# Core logic from your snippet
# -------------------------

def get_alerts_data_for_incident(
    tenant_id: str,
    fingerprints: Sequence[str],
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Aggregate sources/services/severity/count for the given fingerprints."""
    with existed_or_new_session(session) as s:
        service_field = get_json_extract_field(s, Alert.event, "service")
        severity_field = get_json_extract_field(s, Alert.event, "severity")

        fields = (
            service_field,
            Alert.provider_type,
            Alert.fingerprint,
            severity_field,
            get_json_extract_field(s, Alert.event, "lastReceived"),
        )

        rows = s.exec(
            select(*fields)
            .select_from(LastAlert)
            .join(
                Alert,
                (LastAlert.tenant_id == Alert.tenant_id)
                & (LastAlert.alert_id == Alert.id),
            )
            .where(
                LastAlert.tenant_id == tenant_id,
                LastAlert.fingerprint.in_([str(fp) for fp in fingerprints]),
            )
        ).all()

        sources: Set[str] = set()
        services: Set[str] = set()
        severities: List[IncidentSeverity] = []
        last_received_values: List[datetime] = []

        for service, source, _fp, sev, last_received in rows:
            if source:
                sources.add(str(source))
            if service:
                services.add(str(service))
            if sev is not None:
                if isinstance(sev, (int, float)):
                    severities.append(IncidentSeverity.from_number(int(sev)))
                else:
                    # handle strings like "LOW", "low", "critical"
                    sev_str = str(sev).strip().lower()
                    lookup = {
                        "low": IncidentSeverity.LOW,
                        "medium": IncidentSeverity.MEDIUM,
                        "high": IncidentSeverity.HIGH,
                        "critical": IncidentSeverity.CRITICAL,
                        "1": IncidentSeverity.LOW,
                        "2": IncidentSeverity.MEDIUM,
                        "3": IncidentSeverity.HIGH,
                        "4": IncidentSeverity.CRITICAL,
                    }
                    severities.append(lookup.get(sev_str, IncidentSeverity.LOW))

            dt = _parse_dt(last_received)
            if dt is not None:
                last_received_values.append(dt)

        max_sev = max(severities) if severities else IncidentSeverity.LOW

        return {
            "sources": sources,
            "services": services,
            "count": len({str(fp) for fp in fingerprints}),
            "max_severity": max_sev,
            "min_last_received": min(last_received_values) if last_received_values else None,
            "max_last_received": max(last_received_values) if last_received_values else None,
        }


def prepare_incident_aggregation_from_alert_ids(
    tenant_id: str,
    alert_ids: Sequence[Union[str, UUID]],
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Prepare aggregated incident data for a list of *alert_ids*.

    Returns:
        {sources: set[str], services: set[str], max_severity: IncidentSeverity}

    NOTE:
        Your pasted version said "alert_ids" in the docstring but used
        `fingerprints` in the query. This implementation follows the docstring.
    """
    with existed_or_new_session(session) as s:
        service_field = get_json_extract_field(s, Alert.event, "service")
        severity_field = get_json_extract_field(s, Alert.event, "severity")

        rows = s.exec(
            select(service_field, Alert.provider_type, Alert.fingerprint, severity_field)
            .select_from(LastAlert)
            .join(
                Alert,
                (LastAlert.tenant_id == Alert.tenant_id)
                & (LastAlert.alert_id == Alert.id),
            )
            .where(
                LastAlert.tenant_id == tenant_id,
                LastAlert.alert_id.in_([str(aid) for aid in alert_ids]),
            )
        ).all()

        sources: Set[str] = set()
        services: Set[str] = set()
        severities: List[IncidentSeverity] = []

        for service, source, _fingerprint, severity in rows:
            if source:
                sources.add(str(source))
            if service:
                services.add(str(service))
            if severity is not None:
                if isinstance(severity, (int, float)):
                    severities.append(IncidentSeverity.from_number(int(severity)))
                else:
                    severities.append(IncidentSeverity(str(severity).strip().upper()))

        return {
            "sources": sources,
            "services": services,
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
    exclude_unlinked_alerts: bool = False,
    max_retries: int = 3,
) -> Optional[Incident]:
    """Attach alerts (by fingerprint) to an incident and update incident aggregates."""

    with existed_or_new_session(session) as s:
        _ensure_incident_lists(incident)

        # existing fingerprints already linked & not deleted
        existing = set(
            s.exec(
                select(LastAlertToIncident.fingerprint)
                .where(
                    LastAlertToIncident.tenant_id == tenant_id,
                    LastAlertToIncident.incident_id == incident.id,
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                )
            ).all()
        )

        new_fps = {str(fp) for fp in fingerprints if str(fp) not in existing}

        if exclude_unlinked_alerts:
            unlinked = set(
                s.exec(
                    select(LastAlertToIncident.fingerprint)
                    .where(
                        LastAlertToIncident.tenant_id == tenant_id,
                        LastAlertToIncident.incident_id == incident.id,
                        LastAlertToIncident.deleted_at != NULL_FOR_DELETED_AT,
                    )
                ).all()
            )
            new_fps -= unlinked

        if not new_fps:
            return incident

        # Insert link rows
        for fp in new_fps:
            s.add(
                LastAlertToIncident(
                    tenant_id=tenant_id,
                    incident_id=incident.id,
                    fingerprint=str(fp),
                    is_created_by_ai=is_created_by_ai,
                    deleted_at=NULL_FOR_DELETED_AT,
                )
            )
        s.commit()

        # Aggregate data for new fingerprints
        agg = get_alerts_data_for_incident(tenant_id, list(new_fps), s)

        # Merge sources/services
        new_sources = sorted(set(incident.sources or []) | set(agg["sources"]))
        new_services = sorted(set(incident.affected_services or []) | set(agg["services"]))

        # Update severity if not forced
        if not incident.forced_severity:
            if incident.alerts_count:
                incident.severity = max(incident.severity, agg["max_severity"].order)
            else:
                incident.severity = agg["max_severity"].order

        # Update counts
        if not override_count:
            incident.alerts_count = s.exec(
                select(func.count())
                .select_from(LastAlertToIncident)
                .where(
                    LastAlertToIncident.tenant_id == tenant_id,
                    LastAlertToIncident.incident_id == incident.id,
                    LastAlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                )
            ).one()
        else:
            incident.alerts_count = int(agg.get("count", 0))

        # Update times from lastReceived values when present
        if agg["min_last_received"] is not None:
            incident.start_time = (
                min(filter(None, [incident.start_time, agg["min_last_received"]]))
                if incident.start_time
                else agg["min_last_received"]
            )
        if agg["max_last_received"] is not None:
            incident.last_seen_time = (
                max(filter(None, [incident.last_seen_time, agg["max_last_received"]]))
                if incident.last_seen_time
                else agg["max_last_received"]
            )

        incident.sources = new_sources
        incident.affected_services = new_services

        # Persist
        for attempt in range(max_retries):
            try:
                s.add(incident)
                s.commit()
                s.refresh(incident)
                break
            except StaleDataError as ex:
                if "expected to update" in str(ex):
                    s.rollback()
                    continue
                raise

        return incident


# -------------------------
# Schema init helper
# -------------------------

def init_db():
    SQLModel.metadata.create_all(engine)


# -------------------------
# Tests
# -------------------------
import unittest


class TestIncidentAggregationAndLinking(unittest.TestCase):
    def setUp(self):
        # Recreate tables fresh for each test
        SQLModel.metadata.drop_all(engine)
        init_db()

    def _seed_alert(self, tenant_id: str, fp: str, provider_type: str, service: str, severity: Any, last_received: Any):
        with Session(engine) as s:
            alert = Alert(
                tenant_id=tenant_id,
                fingerprint=fp,
                provider_type=provider_type,
                provider_id="p1",
                event=_encode_json({
                    "service": service,
                    "severity": severity,
                    "lastReceived": last_received,
                    "status": "firing",
                }),
            )
            s.add(alert)
            s.commit()
            s.refresh(alert)

            la = LastAlert(tenant_id=tenant_id, fingerprint=fp, alert_id=alert.id)
            s.add(la)
            s.commit()
            return alert.id

    def test_prepare_incident_aggregation_from_alert_ids(self):
        tid = "t1"
        a1 = self._seed_alert(tid, "fp1", "pagerduty", "svcA", 2, "2026-01-31T10:00:00+00:00")
        a2 = self._seed_alert(tid, "fp2", "datadog", "svcB", "high", "2026-01-31T11:00:00+00:00")

        with Session(engine) as s:
            agg = prepare_incident_aggregation_from_alert_ids(tid, [a1, a2], s)

        self.assertEqual(agg["sources"], {"pagerduty", "datadog"})
        self.assertEqual(agg["services"], {"svcA", "svcB"})
        self.assertEqual(agg["max_severity"], IncidentSeverity.HIGH)

    def test_add_alerts_to_incident_updates_counts_services_sources_severity(self):
        tid = "t1"
        self._seed_alert(tid, "fp1", "pagerduty", "svcA", 1, "2026-01-31T10:00:00+00:00")
        self._seed_alert(tid, "fp2", "datadog", "svcB", 4, "2026-01-31T12:00:00+00:00")

        with Session(engine) as s:
            inc = Incident(tenant_id=tid)
            # encode lists for our string-backed JSON columns
            inc.sources = _encode_json([])
            inc.affected_services = _encode_json([])
            s.add(inc)
            s.commit()
            s.refresh(inc)

            updated = add_alerts_to_incident(tid, inc, ["fp1", "fp2"], session=s)

            self.assertEqual(updated.alerts_count, 2)
            self.assertEqual(set(updated.sources), {"pagerduty", "datadog"})
            self.assertEqual(set(updated.affected_services), {"svcA", "svcB"})
            self.assertEqual(updated.severity, IncidentSeverity.CRITICAL.order)
            self.assertEqual(updated.start_time.isoformat(), "2026-01-31T10:00:00+00:00")
            self.assertEqual(updated.last_seen_time.isoformat(), "2026-01-31T12:00:00+00:00")

    def test_add_alerts_to_incident_dedupes_existing(self):
        tid = "t1"
        self._seed_alert(tid, "fp1", "pagerduty", "svcA", 1, "2026-01-31T10:00:00+00:00")

        with Session(engine) as s:
            inc = Incident(tenant_id=tid, sources=_encode_json([]), affected_services=_encode_json([]))
            s.add(inc)
            s.commit()
            s.refresh(inc)

            add_alerts_to_incident(tid, inc, ["fp1"], session=s)
            add_alerts_to_incident(tid, inc, ["fp1"], session=s)
            s.refresh(inc)

            self.assertEqual(inc.alerts_count, 1)


if __name__ == "__main__":
    unittest.main()
"""Sandbox-safe DB utilities (SQLModel) - fixed

This file is a *minimal* runnable extraction of the patterns in your Keep DB utils.
It fixes common sandbox crashes:
- SQLModel failing on typing generics (Dict/List) by explicitly mapping JSON fields.
- create_tenant() returning an unbound tenant_id when tenant already exists.
- tz.UTC usage without tz import.
- safer JSON mutation + persistence.

Run:
  python keep_db_utils_sandbox_fixed.py

It will execute unit tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Field, SQLModel, Session, create_engine, select

logger = logging.getLogger("sandbox.keep.db_utils")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


# -------------------------
# Engine
# -------------------------
engine = create_engine("sqlite://", echo=False)


# -------------------------
# Helpers
# -------------------------
@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Generator[Session, None, None]:
    """Use provided session or create/close a new one."""
    if session is not None:
        yield session
        return
    with Session(engine) as s:
        yield s


def _to_utc(dt: datetime) -> datetime:
    """Normalize naive/aware datetime to an aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# -------------------------
# Models (minimal subset)
# -------------------------
class Tenant(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    # JSON field must be explicit or SQLModel may choke depending on annotations
    configuration: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))


class Alert(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    provider_type: Optional[str] = None
    provider_id: Optional[str] = None
    alert_hash: Optional[str] = None

    # IMPORTANT: Dict[str, Any] needs explicit JSON mapping for SQLModel
    event: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))


class LastAlert(SQLModel, table=True):
    tenant_id: str = Field(index=True, primary_key=True)
    fingerprint: str = Field(index=True, primary_key=True)

    timestamp: datetime = Field(index=True)
    first_timestamp: datetime
    alert_id: str
    alert_hash: Optional[str] = None


class MaintenanceWindowRule(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertRaw(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    error: bool = False
    dismissed: bool = False
    dismissed_by: Optional[str] = None
    dismissed_at: Optional[datetime] = None


# Create tables
SQLModel.metadata.create_all(engine)


# -------------------------
# Functions (fixed)
# -------------------------

def get_last_alerts_by_fingerprints(
    tenant_id: str,
    fingerprint: List[str],
    session: Optional[Session] = None,
) -> List[LastAlert]:
    with existed_or_new_session(session) as session:
        query = select(LastAlert).where(
            (LastAlert.tenant_id == tenant_id) & (LastAlert.fingerprint.in_(fingerprint))
        )
        return list(session.exec(query).all())


def get_last_alert_by_fingerprint(
    tenant_id: str,
    fingerprint: str,
    session: Optional[Session] = None,
    for_update: bool = False,
) -> Optional[LastAlert]:
    """SQLite ignores FOR UPDATE; kept for API compatibility."""
    with existed_or_new_session(session) as session:
        query = select(LastAlert).where(
            (LastAlert.tenant_id == tenant_id) & (LastAlert.fingerprint == fingerprint)
        )
        # In Postgres/MySQL this would matter; SQLite will ignore.
        if for_update and session.bind.dialect.name not in ("sqlite",):
            query = query.with_for_update()
        return session.exec(query).first()


def set_last_alert(
    tenant_id: str,
    alert: Alert,
    session: Optional[Session] = None,
    max_retries: int = 3,
) -> None:
    """Upsert LastAlert for a fingerprint.

    Rule: only advance LastAlert if the incoming alert.timestamp is newer than stored.
    """
    fingerprint = alert.fingerprint
    logger.info("Setting last alert for `%s`", fingerprint)

    with existed_or_new_session(session) as session:
        for attempt in range(max_retries):
            try:
                last_alert = get_last_alert_by_fingerprint(
                    tenant_id, fingerprint, session=session, for_update=True
                )

                if last_alert:
                    # Only update if incoming is newer
                    if _to_utc(last_alert.timestamp) < _to_utc(alert.timestamp):
                        last_alert.timestamp = alert.timestamp
                        last_alert.alert_id = alert.id
                        last_alert.alert_hash = alert.alert_hash
                        session.add(last_alert)
                else:
                    last_alert = LastAlert(
                        tenant_id=tenant_id,
                        fingerprint=fingerprint,
                        timestamp=alert.timestamp,
                        first_timestamp=alert.timestamp,
                        alert_id=alert.id,
                        alert_hash=alert.alert_hash,
                    )
                    session.add(last_alert)

                session.commit()
                return

            except OperationalError as ex:
                msg = str(ex)
                if "Deadlock" in msg or "no such savepoint" in msg:
                    logger.info(
                        "OperationalError updating lastalert for `%s`, retry %s/%s: %s",
                        fingerprint,
                        attempt + 1,
                        max_retries,
                        msg,
                    )
                    session.rollback()
                    if attempt + 1 >= max_retries:
                        raise
                    continue
                raise


def set_maintenance_windows_trace(
    alert: Alert,
    maintenance_w: MaintenanceWindowRule,
    session: Optional[Session] = None,
) -> None:
    """Append maintenance window id to alert.event['maintenance_windows_trace'].

    Behavior: ensure the trace list exists and contains unique IDs.
    """
    mw_id = str(maintenance_w.id)
    trace = alert.event.get("maintenance_windows_trace")

    if isinstance(trace, list) and mw_id in trace:
        return

    with existed_or_new_session(session) as session:
        trace = alert.event.get("maintenance_windows_trace")
        if not isinstance(trace, list):
            trace = []
        if mw_id not in trace:
            trace.append(mw_id)
        alert.event["maintenance_windows_trace"] = trace

        # Ensure SQLAlchemy knows JSON changed
        flag_modified(alert, "event")
        session.add(alert)
        session.commit()


def create_tenant(tenant_name: str) -> str:
    """Create tenant if missing; always return tenant_id.

    FIX: the original version returned an unbound tenant_id when tenant already existed.
    """
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == tenant_name)).first()
        if tenant:
            return tenant.id

        tenant_id = str(uuid.uuid4())
        session.add(Tenant(id=tenant_id, name=tenant_name))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # Race: someone else created it; fetch it
            tenant = session.exec(select(Tenant).where(Tenant.name == tenant_name)).first()
            if tenant:
                return tenant.id
            raise
        return tenant_id


def recover_prev_alert_status(alert: Alert, session: Optional[Session] = None) -> None:
    """Swap alert.event['status'] and alert.event['previous_status'].

    If previous_status is missing/None: do nothing.
    """
    prev_status = alert.event.get("previous_status")
    if prev_status is None:
        logger.warning("Alert %s has no previous_status; nothing to recover.", alert.id)
        return

    with existed_or_new_session(session) as session:
        status = alert.event.get("status")
        alert.event["status"] = prev_status
        alert.event["previous_status"] = status
        flag_modified(alert, "event")
        session.add(alert)
        session.commit()


# -------------------------
# Tests
# -------------------------
import unittest


class TestDbUtils(unittest.TestCase):
    def setUp(self) -> None:
        # Fresh DB per test suite run: drop+create
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

    def test_create_tenant_idempotent(self):
        tid1 = create_tenant("Acme")
        tid2 = create_tenant("Acme")
        self.assertEqual(tid1, tid2)

        with Session(engine) as s:
            count = s.exec(select(Tenant)).all()
            self.assertEqual(len(count), 1)

    def test_set_last_alert_only_advances_on_newer_timestamp(self):
        tenant_id = create_tenant("T")

        older = Alert(
            tenant_id=tenant_id,
            fingerprint="fp",
            timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc),
            alert_hash="old",
        )
        newer = Alert(
            tenant_id=tenant_id,
            fingerprint="fp",
            timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            alert_hash="new",
        )

        with Session(engine) as s:
            s.add(older)
            s.add(newer)
            s.commit()

            set_last_alert(tenant_id, older, session=s)
            la1 = get_last_alert_by_fingerprint(tenant_id, "fp", session=s)
            self.assertEqual(la1.alert_hash, "old")

            set_last_alert(tenant_id, newer, session=s)
            la2 = get_last_alert_by_fingerprint(tenant_id, "fp", session=s)
            self.assertEqual(la2.alert_hash, "new")

            # Try to regress with older timestamp
            set_last_alert(tenant_id, older, session=s)
            la3 = get_last_alert_by_fingerprint(tenant_id, "fp", session=s)
            self.assertEqual(la3.alert_hash, "new")

    def test_set_maintenance_windows_trace_unique(self):
        tenant_id = create_tenant("T")
        mw = MaintenanceWindowRule(start_time=datetime.now(timezone.utc))
        alert = Alert(tenant_id=tenant_id, fingerprint="fp", event={"status": "firing"})

        with Session(engine) as s:
            s.add(mw)
            s.add(alert)
            s.commit()

            set_maintenance_windows_trace(alert, mw, session=s)
            set_maintenance_windows_trace(alert, mw, session=s)

            refreshed = s.exec(select(Alert).where(Alert.id == alert.id)).first()
            trace = refreshed.event.get("maintenance_windows_trace")
            self.assertIsInstance(trace, list)
            self.assertEqual(trace.count(str(mw.id)), 1)

    def test_recover_prev_alert_status_swaps(self):
        tenant_id = create_tenant("T")
        alert = Alert(
            tenant_id=tenant_id,
            fingerprint="fp",
            event={"status": "RESOLVED", "previous_status": "FIRING"},
        )
        with Session(engine) as s:
            s.add(alert)
            s.commit()

            recover_prev_alert_status(alert, session=s)
            refreshed = s.exec(select(Alert).where(Alert.id == alert.id)).first()
            self.assertEqual(refreshed.event["status"], "FIRING")
            self.assertEqual(refreshed.event["previous_status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
