"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

import hashlib
import json
import logging
import random
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Tuple, Type, Union
from uuid import uuid4

import numpy as np
import validators
from dotenv import find_dotenv, load_dotenv
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import (
    String,
    and_,
    case,
    cast,
    desc,
    func,
    literal,
    null,
    select,
    union,
    update,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload, selectinload, subqueryload
from sqlalchemy.sql import exists, expression
from sqlmodel import Session, SQLModel, col, or_, select, text

from keep.api.consts import STATIC_PRESETS
from keep.api.core.db_utils import create_db_engine, get_json_extract_field

# This import is required to create the tables
from keep.api.models.alert import (
    AlertStatus,
    IncidentDto,
    IncidentDtoIn,
    IncidentSorting,
)
from keep.api.models.db.action import Action
from keep.api.models.db.alert import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.dashboard import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.extraction import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.maintenance_window import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.mapping import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.preset import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.provider import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.rule import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.system import * # pylint: disable=unused-wildcard-import
from keep.api.models.db.tenant import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.topology import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-import
from keep.api.models.time_stamp import TimeStampFilter

logger = logging.getLogger(__name__)


# this is a workaround for gunicorn to load the env vars
# because somehow in gunicorn it doesn't load the .env file
load_dotenv(find_dotenv())


engine = create_db_engine()
SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)


ALLOWED_INCIDENT_FILTERS = [
    "status",
    "severity",
    "sources",
    "affected_services",
    "assignee",
]


@contextmanager
def existed_or_new_session(session: Optional[Session] = None) -> Session:
    if session:
        yield session
    else:
        with Session(engine) as session:
            yield session


def get_session() -> Session:
    """
    Creates a database session.

    Yields:
        Session: A database session
    """
    from opentelemetry import trace  # pylint: disable=import-outside-toplevel

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_session"):
        with Session(engine) as session:
            yield session


def get_session_sync() -> Session:
    """
    Creates a database session.

    Returns:
        Session: A database session
    """
    return Session(engine)


def create_workflow_execution(
    workflow_id: str,
    tenant_id: str,
    triggered_by: str,
    execution_number: int = 1,
    event_id: str = None,
    fingerprint: str = None,
    execution_id: str = None,
    event_type: str = "alert",
) -> str:
    with Session(engine) as session:
        try:
            if len(triggered_by) > 255:
                triggered_by = triggered_by[:255]
            workflow_execution = WorkflowExecution(
                id=execution_id or str(uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                started=datetime.now(tz=timezone.utc),
                triggered_by=triggered_by,
                execution_number=execution_number,
                status="in_progress",
            )
            session.add(workflow_execution)
            # Ensure the object has an id
            session.flush()
            execution_id = workflow_execution.id
            if fingerprint and event_type == "alert":
                workflow_to_alert_execution = WorkflowToAlertExecution(
                    workflow_execution_id=execution_id,
                    alert_fingerprint=fingerprint,
                    event_id=event_id,
                )
                session.add(workflow_to_alert_execution)
            elif event_type == "incident":
                workflow_to_incident_execution = WorkflowToIncidentExecution(
                    workflow_execution_id=execution_id,
                    alert_fingerprint=fingerprint,
                    incident_id=event_id,
                )
                session.add(workflow_to_incident_execution)

            session.commit()
            return execution_id
        except IntegrityError:
            session.rollback()
            logger.debug(
                f"Failed to create a new execution for workflow {workflow_id}. Constraint is met."
            )
            raise


def get_mapping_rule_by_id(tenant_id: str, rule_id: str) -> MappingRule | None:
    rule = None
    with Session(engine) as session:
        rule: MappingRule | None = (
            session.query(MappingRule)
            .filter(MappingRule.tenant_id == tenant_id)
            .filter(MappingRule.id == rule_id)
            .first()
        )
    return rule


def get_last_completed_execution(
    session: Session, workflow_id: str
) -> WorkflowExecution:
    return session.exec(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .where(
            (WorkflowExecution.status == "success")
            | (WorkflowExecution.status == "error")
            | (WorkflowExecution.status == "providers_not_configured")
        )
        .order_by(WorkflowExecution.execution_number.desc())
        .limit(1)
    ).first()


def get_workflows_that_should_run():
    with Session(engine) as session:
        logger.debug("Checking for workflows that should run")
        workflows_with_interval = (
            session.query(Workflow)
            .filter(Workflow.is_deleted == False)
            .filter(Workflow.is_disabled == False)
            .filter(Workflow.interval != None)
            .filter(Workflow.interval > 0)
            .all()
        )
        logger.debug(f"Found {len(workflows_with_interval)} workflows with interval")
        workflows_to_run = []
        # for each workflow:
        for workflow in workflows_with_interval:
            current_time = datetime.utcnow()
            last_execution = get_last_completed_execution(session, workflow.id)
            # if there no last execution, that's the first time we run the workflow
            if not last_execution:
                try:
                    # try to get the lock
                    workflow_execution_id = create_workflow_execution(
                        workflow.id, workflow.tenant_id, "scheduler"
                    )
                    # we succeed to get the lock on this execution number :)
                    # let's run it
                    workflows_to_run.append(
                        {
                            "tenant_id": workflow.tenant_id,
                            "workflow_id": workflow.id,
                            "workflow_execution_id": workflow_execution_id,
                        }
                    )
                # some other thread/instance has already started to work on it
                except IntegrityError:
                    continue
            # else, if the last execution was more than interval seconds ago, we need to run it
            elif (
                last_execution.started + timedelta(seconds=workflow.interval)
                <= current_time
            ):
                try:
                    # try to get the lock with execution_number + 1
                    workflow_execution_id = create_workflow_execution(
                        workflow.id,
                        workflow.tenant_id,
                        "scheduler",
                        last_execution.execution_number + 1,
                    )
                    # we succeed to get the lock on this execution number :)
                    # let's run it
                    workflows_to_run.append(
                        {
                            "tenant_id": workflow.tenant_id,
                            "workflow_id": workflow.id,
                            "workflow_execution_id": workflow_execution_id,
                        }
                    )
                    # continue to the next one
                    continue
                # some other thread/instance has already started to work on it
                except IntegrityError:
                    # we need to verify the locking is still valid and not timeouted
                    session.rollback()
                    pass
                # get the ongoing execution
                ongoing_execution = session.exec(
                    select(WorkflowExecution)
                    .where(WorkflowExecution.workflow_id == workflow.id)
                    .where(
                        WorkflowExecution.execution_number
                        == last_execution.execution_number + 1
                    )
                    .limit(1)
                ).first()
                # this is a WTF exception since if this (workflow_id, execution_number) does not exist,
                # we would be able to acquire the lock
                if not ongoing_execution:
                    logger.error(
                        f"WTF: ongoing execution not found {workflow.id} {last_execution.execution_number + 1}"
                    )
                    continue
                # if this completed, error, than that's ok - the service who locked the execution is done
                elif ongoing_execution.status != "in_progress":
                    continue
                # if the ongoing execution runs more than 60 minutes, than its timeout
                elif ongoing_execution.started + timedelta(minutes=60) <= current_time:
                    ongoing_execution.status = "timeout"
                    session.commit()
                    # re-create the execution and try to get the lock
                    try:
                        workflow_execution_id = create_workflow_execution(
                            workflow.id,
                            workflow.tenant_id,
                            "scheduler",
                            ongoing_execution.execution_number + 1,
                        )
                    # some other thread/instance has already started to work on it and that's ok
                    except IntegrityError:
                        logger.debug(
                            f"Failed to create a new execution for workflow {workflow.id} [timeout]. Constraint is met."
                        )
                        continue
                    # managed to acquire the (workflow_id, execution_number) lock
                    workflows_to_run.append(
                        {
                            "tenant_id": workflow.tenant_id,
                            "workflow_id": workflow.id,
                            "workflow_execution_id": workflow_execution_id,
                        }
                    )
            else:
                logger.debug(
                    f"Workflow {workflow.id} is already running by someone else"
                )

        return workflows_to_run


def add_or_update_workflow(
    id,
    name,
    tenant_id,
    description,
    created_by,
    interval,
    workflow_raw,
    is_disabled,
    provisioned=False,
    provisioned_file=None,
    updated_by=None,
) -> Workflow:
    with Session(engine, expire_on_commit=False) as session:
        # TODO: we need to better understanad if that's the right behavior we want
        existing_workflow = (
            session.query(Workflow)
            .filter_by(name=name)
            .filter_by(tenant_id=tenant_id)
            .first()
        )

        if existing_workflow:
            # tb: no need to override the id field here because it has foreign key constraints.
            existing_workflow.tenant_id = tenant_id
            existing_workflow.description = description
            existing_workflow.updated_by = (
                updated_by or existing_workflow.updated_by
            )  # Update the updated_by field if provided
            existing_workflow.interval = interval
            existing_workflow.workflow_raw = workflow_raw
            existing_workflow.revision += 1  # Increment the revision
            existing_workflow.last_updated = datetime.now()  # Update last_updated
            existing_workflow.is_deleted = False
            existing_workflow.is_disabled = is_disabled
            existing_workflow.provisioned = provisioned
            existing_workflow.provisioned_file = provisioned_file

        else:
            # Create a new workflow
            workflow = Workflow(
                id=id,
                name=name,
                tenant_id=tenant_id,
                description=description,
                created_by=created_by,
                updated_by=updated_by,  # Set updated_by to the provided value
                interval=interval,
                is_disabled=is_disabled,
                workflow_raw=workflow_raw,
                provisioned=provisioned,
                provisioned_file=provisioned_file,
            )
            session.add(workflow)

        session.commit()
        return existing_workflow if existing_workflow else workflow


def get_workflow_to_alert_execution_by_workflow_execution_id(
    workflow_execution_id: str,
) -> WorkflowToAlertExecution:
    """
    Get the WorkflowToAlertExecution entry for a given workflow execution ID.

    Args:
        workflow_execution_id (str): The workflow execution ID to filter the workflow execution by.

    Returns:
        WorkflowToAlertExecution: The WorkflowToAlertExecution object.
    """
    with Session(engine) as session:
        return (
            session.query(WorkflowToAlertExecution)
            .filter_by(workflow_execution_id=workflow_execution_id)
            .first()
        )


def get_last_workflow_workflow_to_alert_executions(
    session: Session, tenant_id: str
) -> list[WorkflowToAlertExecution]:
    """
    Get the latest workflow executions for each alert fingerprint.

    Args:
        session (Session): The database session.
        tenant_id (str): The tenant_id to filter the workflow executions by.

    Returns:
        list[WorkflowToAlertExecution]: A list of WorkflowToAlertExecution objects.
    """
    # Subquery to find the max started timestamp for each alert_fingerprint
    max_started_subquery = (
        session.query(
            WorkflowToAlertExecution.alert_fingerprint,
            func.max(WorkflowExecution.started).label("max_started"),
        )
        .join(
            WorkflowExecution,
            WorkflowToAlertExecution.workflow_execution_id == WorkflowExecution.id,
        )
        .filter(WorkflowExecution.tenant_id == tenant_id)
        .filter(WorkflowExecution.started >= datetime.now() - timedelta(days=7))
        .group_by(WorkflowToAlertExecution.alert_fingerprint)
    ).subquery("max_started_subquery")

    # Query to find WorkflowToAlertExecution entries that match the max started timestamp
    latest_workflow_to_alert_executions: list[WorkflowToAlertExecution] = (
        session.query(WorkflowToAlertExecution)
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
        .filter(WorkflowExecution.tenant_id == tenant_id)
        .limit(1000)
        .all()
    )
    return latest_workflow_to_alert_executions


def get_last_workflow_execution_by_workflow_id(
    tenant_id: str, workflow_id: str
) -> Optional[WorkflowExecution]:
    with Session(engine) as session:
        workflow_execution = (
            session.query(WorkflowExecution)
            .filter(WorkflowExecution.workflow_id == workflow_id)
            .filter(WorkflowExecution.tenant_id == tenant_id)
            .filter(WorkflowExecution.started >= datetime.now() - timedelta(days=7))
            .filter(WorkflowExecution.status == "success")
            .order_by(WorkflowExecution.started.desc())
            .first()
        )
    return workflow_execution


def get_workflows_with_last_execution(tenant_id: str) -> List[dict]:
    with Session(engine) as session:
        latest_execution_cte = (
            select(
                WorkflowExecution.workflow_id,
                func.max(WorkflowExecution.started).label("last_execution_time"),
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(
                WorkflowExecution.started
                >= datetime.now(tz=timezone.utc) - timedelta(days=7)
            )
            .group_by(WorkflowExecution.workflow_id)
            .limit(1000)
            .cte("latest_execution_cte")
        )

        workflows_with_last_execution_query = (
            select(
                Workflow,
                latest_execution_cte.c.last_execution_time,
                WorkflowExecution.status,
            )
            .outerjoin(
                latest_execution_cte,
                Workflow.id == latest_execution_cte.c.workflow_id,
            )
            .outerjoin(
                WorkflowExecution,
                and_(
                    Workflow.id == WorkflowExecution.workflow_id,
                    WorkflowExecution.started
                    == latest_execution_cte.c.last_execution_time,
                ),
            )
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted == False)
        ).distinct()

        result = session.execute(workflows_with_last_execution_query).all()
    return result


def get_all_workflows(tenant_id: str) -> List[Workflow]:
    with Session(engine) as session:
        workflows = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted == False)
        ).all()
    return workflows


def get_all_provisioned_workflows(tenant_id: str) -> List[Workflow]:
    with Session(engine) as session:
        workflows = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.provisioned == True)
            .where(Workflow.is_deleted == False)
        ).all()
    return workflows


def get_all_provisioned_providers(tenant_id: str) -> List[Provider]:
    with Session(engine) as session:
        providers = session.exec(
            select(Provider)
            .where(Provider.tenant_id == tenant_id)
            .where(Provider.provisioned == True)
        ).all()
    return providers


def get_all_workflows_yamls(tenant_id: str) -> List[str]:
    with Session(engine) as session:
        workflows = session.exec(
            select(Workflow.workflow_raw)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted == False)
        ).all()
    return workflows


def get_workflow(tenant_id: str, workflow_id: str) -> Workflow:
    with Session(engine) as session:
        # if the workflow id is uuid:
        if validators.uuid(workflow_id):
            workflow = session.exec(
                select(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.id == workflow_id)
                .where(Workflow.is_deleted == False)
            ).first()
        else:
            workflow = session.exec(
                select(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.name == workflow_id)
                .where(Workflow.is_deleted == False)
            ).first()
    if not workflow:
        return None
    return workflow


def get_raw_workflow(tenant_id: str, workflow_id: str) -> str:
    workflow = get_workflow(tenant_id, workflow_id)
    if not workflow:
        return None
    return workflow.workflow_raw


def update_provider_last_pull_time(tenant_id: str, provider_id: str):
    extra = {"tenant_id": tenant_id, "provider_id": provider_id}
    logger.info("Updating provider last pull time", extra=extra)
    with Session(engine) as session:
        provider = session.exec(
            select(Provider).where(
                Provider.tenant_id == tenant_id, Provider.id == provider_id
            )
        ).first()

        if not provider:
            logger.warning(
                "Could not update provider last pull time since provider does not exist",
                extra=extra,
            )

        try:
            provider.last_pull_time = datetime.now(tz=timezone.utc)
            session.commit()
        except Exception:
            logger.exception("Failed to update provider last pull time", extra=extra)
            raise
    logger.info("Successfully updated provider last pull time", extra=extra)


def get_installed_providers(tenant_id: str) -> List[Provider]:
    with Session(engine) as session:
        providers = session.exec(
            select(Provider).where(Provider.tenant_id == tenant_id)
        ).all()
    return providers


def get_consumer_providers() -> List[Provider]:
    # get all the providers that installed as consumers
    with Session(engine) as session:
        providers = session.exec(
            select(Provider).where(Provider.consumer == True)
        ).all()
    return providers


def finish_workflow_execution(tenant_id, workflow_id, execution_id, status, error):
    with Session(engine) as session:
        workflow_execution = session.exec(
            select(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .where(WorkflowExecution.id == execution_id)
        ).first()
        # some random number to avoid collisions
        if not workflow_execution:
            logger.warning(
                f"Failed to finish workflow execution {execution_id} for workflow {workflow_id}. Execution not found."
            )
            raise ValueError("Execution not found")
        workflow_execution.is_running = random.randint(1, 2147483647 - 1)  # max int
        workflow_execution.status = status
        # TODO: we had a bug with the error field, it was too short so some customers may fail over it.
        #   we need to fix it in the future, create a migration that increases the size of the error field
        #   and then we can remove the [:255] from here
        workflow_execution.error = error[:255] if error else None
        workflow_execution.execution_time = (
            datetime.utcnow() - workflow_execution.started
        ).total_seconds()
        # TODO: logs
        session.commit()


def get_workflow_executions(
    tenant_id,
    workflow_id,
    limit=50,
    offset=0,
    tab=2,
    status: Optional[Union[str, List[str]]] = None,
    trigger: Optional[Union[str, List[str]]] = None,
    execution_id: Optional[str] = None,
):
    with Session(engine) as session:
        query = session.query(
            WorkflowExecution,
        ).filter(
            WorkflowExecution.tenant_id == tenant_id,
            WorkflowExecution.workflow_id == workflow_id,
        )

        now = datetime.now(tz=timezone.utc)
        timeframe = None

        if tab == 1:
            timeframe = now - timedelta(days=30)
        elif tab == 2:
            timeframe = now - timedelta(days=7)
        elif tab == 3:
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(
                WorkflowExecution.started >= start_of_day,
                WorkflowExecution.started <= now,
            )

        if timeframe:
            query = query.filter(WorkflowExecution.started >= timeframe)

        if isinstance(status, str):
            status = [status]
        elif status is None:
            status = []

        # Normalize trigger to a list
        if isinstance(trigger, str):
            trigger = [trigger]

        if execution_id:
            query = query.filter(WorkflowExecution.id == execution_id)
        if status and len(status) > 0:
            query = query.filter(WorkflowExecution.status.in_(status))
        if trigger and len(trigger) > 0:
            conditions = [
                WorkflowExecution.triggered_by.like(f"{trig}%") for trig in trigger
            ]
            query = query.filter(or_(*conditions))

        total_count = query.count()
        status_count_query = query.with_entities(
            WorkflowExecution.status, func.count().label("count")
        ).group_by(WorkflowExecution.status)
        status_counts = status_count_query.all()

        statusGroupbyMap = {status: count for status, count in status_counts}
        pass_count = statusGroupbyMap.get("success", 0)
        fail_count = statusGroupbyMap.get("error", 0) + statusGroupbyMap.get(
            "timeout", 0
        )
        avgDuration = query.with_entities(
            func.avg(WorkflowExecution.execution_time)
        ).scalar()
        avgDuration = avgDuration if avgDuration else 0.0

        query = (
            query.order_by(desc(WorkflowExecution.started)).limit(limit).offset(offset)
        )
        # Execute the query
        workflow_executions = query.all()

    return total_count, workflow_executions, pass_count, fail_count, avgDuration


def delete_workflow(tenant_id, workflow_id):
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.id == workflow_id)
        ).first()

        if workflow:
            workflow.is_deleted = True
            session.commit()


def delete_workflow_by_provisioned_file(tenant_id, provisioned_file):
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.provisioned_file == provisioned_file)
        ).first()

        if workflow:
            workflow.is_deleted = True
            session.commit()


def get_workflow_id(tenant_id, workflow_name):
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.name == workflow_name)
            .where(Workflow.is_deleted == False)
        ).first()

        if workflow:
            return workflow.id


def push_logs_to_db(log_entries):
    # avoid circular import
    from keep.api.logging import LOG_FORMAT, LOG_FORMAT_OPEN_TELEMETRY

    if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY:
        db_log_entries = [
            WorkflowExecutionLog(
                workflow_execution_id=log_entry["workflow_execution_id"],
                timestamp=datetime.strptime(
                    log_entry["asctime"], "%Y-%m-%d %H:%M:%S,%f"
                ),
                message=log_entry["message"][0:255],  # limit the message to 255 chars
                context=json.loads(
                    json.dumps(log_entry.get("context", {}), default=str)
                ),  # workaround to serialize any object
            )
            for log_entry in log_entries
        ]
    else:
        db_log_entries = [
            WorkflowExecutionLog(
                workflow_execution_id=log_entry["workflow_execution_id"],
                timestamp=log_entry["created"],
                message=log_entry["message"][0:255],  # limit the message to 255 chars
                context=json.loads(
                    json.dumps(log_entry.get("context", {}), default=str)
                ),  # workaround to serialize any object
            )
            for log_entry in log_entries
        ]

    # Add the LogEntry instances to the database session
    with Session(engine) as session:
        session.add_all(db_log_entries)
        session.commit()


def get_workflow_execution(tenant_id: str, workflow_execution_id: str):
    with Session(engine) as session:
        execution_with_logs = (
            session.query(WorkflowExecution)
            .filter(
                WorkflowExecution.id == workflow_execution_id,
                WorkflowExecution.tenant_id == tenant_id,
            )
            .options(joinedload(WorkflowExecution.logs))
            .one()
        )
    return execution_with_logs


def get_last_workflow_executions(tenant_id: str, limit=20):
    with Session(engine) as session:
        execution_with_logs = (
            session.query(WorkflowExecution)
            .filter(
                WorkflowExecution.tenant_id == tenant_id,
            )
            .order_by(desc(WorkflowExecution.started))
            .limit(limit)
            .options(joinedload(WorkflowExecution.logs))
            .all()
        )

        return execution_with_logs


def get_workflow_executions_count(tenant_id: str):
    with Session(engine) as session:
        query = session.query(WorkflowExecution).filter(
            WorkflowExecution.tenant_id == tenant_id,
        )

        return {
            "success": query.filter(WorkflowExecution.status == "success").count(),
            "other": query.filter(WorkflowExecution.status != "success").count(),
        }


def add_audit(
    tenant_id: str,
    fingerprint: str,
    user_id: str,
    action: AlertActionType,
    description: str,
) -> AlertAudit:
    with Session(engine) as session:
        audit = AlertAudit(
            tenant_id=tenant_id,
            fingerprint=fingerprint,
            user_id=user_id,
            action=action.value,
            description=description,
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
    return audit


def _enrich_alert(
    session,
    tenant_id,
    fingerprint,
    enrichments,
    action_type: AlertActionType,
    action_callee: str,
    action_description: str,
    force=False,
    audit_enabled=True,
):
    """
    Enrich an alert with the provided enrichments.

    Args:
        session (Session): The database session.
        tenant_id (str): The tenant ID to filter the alert enrichments by.
        fingerprint (str): The alert fingerprint to filter the alert enrichments by.
        enrichments (dict): The enrichments to add to the alert.
        force (bool): Whether to force the enrichment to be updated. This is used to dispose enrichments if necessary.
    """
    enrichment = get_enrichment_with_session(session, tenant_id, fingerprint)
    if enrichment:
        # if force - override exisitng enrichments. being used to dispose enrichments if necessary
        if force:
            new_enrichment_data = enrichments
        else:
            new_enrichment_data = {**enrichment.enrichments, **enrichments}
        # SQLAlchemy doesn't support updating JSON fields, so we need to do it manually
        # https://github.com/sqlalchemy/sqlalchemy/discussions/8396#discussion-4308891
        stmt = (
            update(AlertEnrichment)
            .where(AlertEnrichment.id == enrichment.id)
            .values(enrichments=new_enrichment_data)
        )
        session.execute(stmt)
        if audit_enabled:
            # add audit event
            audit = AlertAudit(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                user_id=action_callee,
                action=action_type.value,
                description=action_description,
            )
            session.add(audit)
        session.commit()
        # Refresh the instance to get updated data from the database
        session.refresh(enrichment)
        return enrichment
    else:
        alert_enrichment = AlertEnrichment(
            tenant_id=tenant_id,
            alert_fingerprint=fingerprint,
            enrichments=enrichments,
        )
        session.add(alert_enrichment)
        # add audit event
        if audit_enabled:
            audit = AlertAudit(
                tenant_id=tenant_id,
                fingerprint=fingerprint,
                user_id=action_callee,
                action=action_type.value,
                description=action_description,
            )
            session.add(audit)
        session.commit()
        return alert_enrichment


def enrich_alert(
    tenant_id,
    fingerprint,
    enrichments,
    action_type: AlertActionType,
    action_callee: str,
    action_description: str,
    session=None,
    force=False,
    audit_enabled=True,
):
    # else, the enrichment doesn't exist, create it
    if not session:
        with Session(engine) as session:
            return _enrich_alert(
                session,
                tenant_id,
                fingerprint,
                enrichments,
                action_type,
                action_callee,
                action_description,
                force=force,
                audit_enabled=audit_enabled,
            )
    return _enrich_alert(
        session,
        tenant_id,
        fingerprint,
        enrichments,
        action_type,
        action_callee,
        action_description,
        force=force,
        audit_enabled=audit_enabled,
    )


def count_alerts(
    provider_type: str,
    provider_id: str,
    ever: bool,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    tenant_id: str,
):
    with Session(engine) as session:
        if ever:
            return (
                session.query(Alert)
                .filter(
                    Alert.tenant_id == tenant_id,
                    Alert.provider_id == provider_id,
                    Alert.provider_type == provider_type,
                )
                .count()
            )
        else:
            return (
                session.query(Alert)
                .filter(
                    Alert.tenant_id == tenant_id,
                    Alert.provider_id == provider_id,
                    Alert.provider_type == provider_type,
                    Alert.timestamp >= start_time,
                    Alert.timestamp <= end_time,
                )
                .count()
            )


def get_enrichment(tenant_id, fingerprint, refresh=False):
    with Session(engine) as session:
        return get_enrichment_with_session(session, tenant_id, fingerprint, refresh)


def get_enrichments(
    tenant_id: int, fingerprints: List[str]
) -> List[Optional[AlertEnrichment]]:
    """
    Get a list of alert enrichments for a list of fingerprints using a single DB query.

    :param tenant_id: The tenant ID to filter the alert enrichments by.
    :param fingerprints: A list of fingerprints to get the alert enrichments for.
    :return: A list of AlertEnrichment objects or None for each fingerprint.
    """
    with Session(engine) as session:
        result = session.exec(
            select(AlertEnrichment)
            .where(AlertEnrichment.tenant_id == tenant_id)
            .where(AlertEnrichment.alert_fingerprint.in_(fingerprints))
        ).all()
    return result


def get_enrichment_with_session(session, tenant_id, fingerprint, refresh=False):
    alert_enrichment = session.exec(
        select(AlertEnrichment)
        .where(AlertEnrichment.tenant_id == tenant_id)
        .where(AlertEnrichment.alert_fingerprint == fingerprint)
    ).first()
    if refresh and alert_enrichment:
        try:
            session.refresh(alert_enrichment)
        except Exception:
            logger.exception(
                "Failed to refresh enrichment",
                extra={"tenant_id": tenant_id, "fingerprint": fingerprint},
            )
    return alert_enrichment


def get_alerts_with_filters(
    tenant_id,
    provider_id=None,
    filters=None,
    time_delta=1,
    with_incidents=False,
) -> list[Alert]:
    with Session(engine) as session:
        # Create the query
        query = session.query(Alert)

        # Apply subqueryload to force-load the alert_enrichment relationship
        query = query.options(subqueryload(Alert.alert_enrichment))
        if with_incidents:
            query = query.options(joinedload(Alert.incidents))

        # Filter by tenant_id
        query = query.filter(Alert.tenant_id == tenant_id)

        # Filter by time_delta
        query = query.filter(
            Alert.timestamp
            >= datetime.now(tz=timezone.utc) - timedelta(days=time_delta)
        )

        # Ensure Alert and AlertEnrichment are joined for subsequent filters
        query = query.outerjoin(Alert.alert_enrichment)

        # Apply filters if provided
        if filters:
            for f in filters:
                filter_key, filter_value = f.get("key"), f.get("value")
                if isinstance(filter_value, bool) and filter_value is True:
                    # If the filter value is True, we want to filter by the existence of the enrichment
                    #   e.g.: all the alerts that have ticket_id
                    if session.bind.dialect.name in ["mysql", "postgresql"]:
                        query = query.filter(
                            func.json_extract(
                                AlertEnrichment.enrichments, f"$.{filter_key}"
                            )
                            != null()
                        )
                    elif session.bind.dialect.name == "sqlite":
                        query = query.filter(
                            func.json_type(
                                AlertEnrichment.enrichments, f"$.{filter_key}"
                            )
                            != null()
                        )
                elif isinstance(filter_value, (str, int)):
                    if session.bind.dialect.name in ["mysql", "postgresql"]:
                        query = query.filter(
                            func.json_unquote(
                                func.json_extract(
                                    AlertEnrichment.enrichments, f"$.{filter_key}"
                                )
                            )
                            == filter_value
                        )
                    elif session.bind.dialect.name == "sqlite":
                        query = query.filter(
                            func.json_extract(
                                AlertEnrichment.enrichments, f"$.{filter_key}"
                            )
                            == filter_value
                        )
                    else:
                        logger.warning(
                            "Unsupported dialect",
                            extra={"dialect": session.bind.dialect.name},
                        )
                else:
                    logger.warning("Unsupported filter type", extra={"filter": f})

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        query = query.order_by(Alert.timestamp.desc())

        query = query.limit(10000)

        # Execute the query
        alerts = query.all()

    return alerts


def query_alerts(
    tenant_id,
    provider_id=None,
    limit=1000,
    timeframe=None,
    upper_timestamp=None,
    lower_timestamp=None,
    skip_alerts_with_null_timestamp=True,
    sort_ascending=False,
) -> list[Alert]:
    """
    Get all alerts for a given tenant_id.

    Args:
        tenant_id (_type_): The tenant_id to filter the alerts by.
        provider_id (_type_, optional): The provider id to filter by. Defaults to None.
        limit (_type_, optional): The maximum number of alerts to return. Defaults to 1000.
        timeframe (_type_, optional): The number of days to look back for alerts. Defaults to None.
        upper_timestamp (_type_, optional): The upper timestamp to filter by. Defaults to None.
        lower_timestamp (_type_, optional): The lower timestamp to filter by. Defaults to None.

    Returns:
        List[Alert]: A list of Alert objects."""

    with Session(engine) as session:
        # Create the query
        query = session.query(Alert)

        # Apply subqueryload to force-load the alert_enrichment relationship
        query = query.options(subqueryload(Alert.alert_enrichment))

        # Filter by tenant_id
        query = query.filter(Alert.tenant_id == tenant_id)

        # if timeframe is provided, filter the alerts by the timeframe
        if timeframe:
            query = query.filter(
                Alert.timestamp
                >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
            )

        filter_conditions = []

        if upper_timestamp is not None:
            filter_conditions.append(Alert.timestamp < upper_timestamp)

        if lower_timestamp is not None:
            filter_conditions.append(Alert.timestamp >= lower_timestamp)

        # Apply the filter conditions
        if filter_conditions:
            query = query.filter(*filter_conditions)  # Unpack and apply all conditions

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        if skip_alerts_with_null_timestamp:
            query = query.filter(Alert.timestamp.isnot(None))

        if sort_ascending:
            query = query.order_by(Alert.timestamp.asc())
        else:
            query = query.order_by(Alert.timestamp.desc())

        if limit:
            query = query.limit(limit)

        # Execute the query
        alerts = query.all()

    return alerts


def get_last_alerts(
    tenant_id,
    provider_id=None,
    limit=1000,
    timeframe=None,
    upper_timestamp=None,
    lower_timestamp=None,
    with_incidents=False,
    fingerprints=None,
) -> list[Alert]:
    """
    Get the last alert for each fingerprint along with the first time the alert was triggered.
    Supports MySQL, PostgreSQL, and SQLite databases.

    Args:
        tenant_id (_type_): The tenant_id to filter the alerts by.
        provider_id (_type_, optional): The provider id to filter by. Defaults to None.
        limit (int, optional): The maximum number of alerts to return. Defaults to 1000.
        timeframe (int, optional): The number of days to look back. Defaults to None.
        upper_timestamp (datetime, optional): The upper bound for the timestamp filter. Defaults to None.
        lower_timestamp (datetime, optional): The lower bound for the timestamp filter. Defaults to None.
        fingerprints (List[str], optional): List of fingerprints to filter by. Defaults to None.

    Returns:
        List[Alert]: A list of Alert objects including the first time the alert was triggered.
    """
    with Session(engine) as session:
        dialect_name = session.bind.dialect.name

        # Subquery that selects the max and min timestamp for each fingerprint
        subquery = (
            session.query(
                Alert.fingerprint,
                func.max(Alert.timestamp).label("max_timestamp"),
                func.min(Alert.timestamp).label("min_timestamp"),
            )
            .filter(Alert.tenant_id == tenant_id)
            .group_by(Alert.fingerprint)
            .subquery()
        )

        # Apply timeframe filter if provided
        if timeframe:
            subquery = (
                session.query(subquery)
                .filter(
                    subquery.c.max_timestamp
                    >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
                )
                .subquery()
            )

        # Apply additional filters
        filter_conditions = []

        if upper_timestamp is not None:
            filter_conditions.append(subquery.c.max_timestamp < upper_timestamp)

        if lower_timestamp is not None:
            filter_conditions.append(subquery.c.max_timestamp >= lower_timestamp)

        if fingerprints:
            filter_conditions.append(subquery.c.fingerprint.in_(tuple(fingerprints)))

        logger.info(f"filter_conditions: {filter_conditions}")

        if filter_conditions:
            subquery = session.query(subquery).filter(*filter_conditions).subquery()

        # Main query for alerts
        query = (
            session.query(
                Alert,
                subquery.c.min_timestamp.label("startedAt"),
            )
            .filter(Alert.tenant_id == tenant_id)
            .join(
                subquery,
                and_(
                    Alert.fingerprint == subquery.c.fingerprint,
                    Alert.timestamp == subquery.c.max_timestamp,
                ),
            )
            .options(subqueryload(Alert.alert_enrichment))
        )

        if with_incidents:
            if dialect_name == "sqlite":
                # SQLite version - using JSON
                incidents_subquery = (
                    session.query(
                        AlertToIncident.alert_id,
                        func.json_group_array(
                            cast(AlertToIncident.incident_id, String)
                        ).label("incidents"),
                    )
                    .filter(AlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
                    .group_by(AlertToIncident.alert_id)
                    .subquery()
                )

            elif dialect_name == "mysql":
                # MySQL version - using GROUP_CONCAT
                incidents_subquery = (
                    session.query(
                        AlertToIncident.alert_id,
                        func.group_concat(
                            cast(AlertToIncident.incident_id, String)
                        ).label("incidents"),
                    )
                    .filter(AlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
                    .group_by(AlertToIncident.alert_id)
                    .subquery()
                )

            elif dialect_name == "postgresql":
                # PostgreSQL version - using string_agg
                incidents_subquery = (
                    session.query(
                        AlertToIncident.alert_id,
                        func.string_agg(
                            cast(AlertToIncident.incident_id, String),
                            ",",
                        ).label("incidents"),
                    )
                    .filter(AlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
                    .group_by(AlertToIncident.alert_id)
                    .subquery()
                )
            else:
                raise ValueError(f"Unsupported dialect: {dialect_name}")

            query = query.add_columns(incidents_subquery.c.incidents)
            query = query.outerjoin(
                incidents_subquery, Alert.id == incidents_subquery.c.alert_id
            )

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        # Order by timestamp in descending order and limit the results
        query = query.order_by(desc(Alert.timestamp)).limit(limit)

        # Execute the query
        alerts_with_start = query.all()

        # Process results based on dialect
        alerts = []
        for alert_data in alerts_with_start:
            alert = alert_data[0]
            startedAt = alert_data[1]
            alert.event["startedAt"] = str(startedAt)
            alert.event["event_id"] = str(alert.id)

            if with_incidents:
                incident_id = alert_data[2]
                if dialect_name == "sqlite":
                    # Parse JSON array for SQLite
                    incident_id = json.loads(incident_id)[0] if incident_id else None
                elif dialect_name in ("mysql", "postgresql"):
                    # Split comma-separated string for MySQL and PostgreSQL
                    incident_id = incident_id.split(",")[0] if incident_id else None

                alert.event["incident"] = str(incident_id) if incident_id else None

            alerts.append(alert)

        return alerts


def get_alerts_by_fingerprint(
    tenant_id: str, fingerprint: str, limit=1, status=None
) -> List[Alert]:
    """
    Get all alerts for a given fingerprint.

    Args:
        tenant_id (str): The tenant_id to filter the alerts by.
        fingerprint (str): The fingerprint to filter the alerts by.

    Returns:
        List[Alert]: A list of Alert objects.
    """
    with Session(engine) as session:
        # Create the query
        query = session.query(Alert)

        # Apply subqueryload to force-load the alert_enrichment relationship
        query = query.options(subqueryload(Alert.alert_enrichment))

        # Filter by tenant_id
        query = query.filter(Alert.tenant_id == tenant_id)

        query = query.filter(Alert.fingerprint == fingerprint)

        query = query.order_by(Alert.timestamp.desc())

        if status:
            query = query.filter(func.json_extract(Alert.event, "$.status") == status)

        if limit:
            query = query.limit(limit)
        # Execute the query
        alerts = query.all()

    return alerts


def get_alert_by_fingerprint_and_event_id(
    tenant_id: str, fingerprint: str, event_id: str
) -> Alert:
    with Session(engine) as session:
        alert = (
            session.query(Alert)
            .filter(Alert.tenant_id == tenant_id)
            .filter(Alert.fingerprint == fingerprint)
            .filter(Alert.id == uuid.UUID(event_id))
            .first()
        )
    return alert


def get_previous_alert_by_fingerprint(tenant_id: str, fingerprint: str) -> Alert:
    # get the previous alert for a given fingerprint
    with Session(engine) as session:
        alert = (
            session.query(Alert)
            .filter(Alert.tenant_id == tenant_id)
            .filter(Alert.fingerprint == fingerprint)
            .order_by(Alert.timestamp.desc())
            .limit(2)
            .all()
        )
    if len(alert) > 1:
        return alert[1]
    else:
        # no previous alert
        return None


def get_api_key(api_key: str) -> TenantApiKey:
    with Session(engine) as session:
        api_key_hashed = hashlib.sha256(api_key.encode()).hexdigest()
        statement = select(TenantApiKey).where(TenantApiKey.key_hash == api_key_hashed)
        tenant_api_key = session.exec(statement).first()
    return tenant_api_key


def get_user_by_api_key(api_key: str):
    api_key = get_api_key(api_key)
    return api_key.created_by


# this is only for single tenant
def get_user(username, password, update_sign_in=True):
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.api.models.db.user import User

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    with Session(engine, expire_on_commit=False) as session:
        user = session.exec(
            select(User)
            .where(User.tenant_id == SINGLE_TENANT_UUID)
            .where(User.username == username)
            .where(User.password_hash == password_hash)
        ).first()
        if user and update_sign_in:
            user.last_sign_in = datetime.utcnow()
            session.add(user)
            session.commit()
    return user


def get_users(tenant_id=None):
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.api.models.db.user import User

    tenant_id = tenant_id or SINGLE_TENANT_UUID

    with Session(engine) as session:
        users = session.exec(select(User).where(User.tenant_id == tenant_id)).all()
    return users


def delete_user(username):
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.api.models.db.user import User

    with Session(engine) as session:
        user = session.exec(
            select(User)
            .where(User.tenant_id == SINGLE_TENANT_UUID)
            .where(User.username == username)
        ).first()
        if user:
            session.delete(user)
            session.commit()


def user_exists(tenant_id, username):
    from keep.api.models.db.user import User

    with Session(engine) as session:
        user = session.exec(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.username == username)
        ).first()
        return user is not None


def create_user(tenant_id, username, password, role):
    from keep.api.models.db.user import User

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    with Session(engine) as session:
        user = User(
            tenant_id=tenant_id,
            username=username,
            password_hash=password_hash,
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def update_user_last_sign_in(tenant_id, username):
    from keep.api.models.db.user import User

    with Session(engine) as session:
        user = session.exec(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.username == username)
        ).first()
        if user:
            user.last_sign_in = datetime.utcnow()
            session.add(user)
            session.commit()
    return user


def update_user_role(tenant_id, username, role):
    from keep.api.models.db.user import User

    with Session(engine) as session:
        user = session.exec(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.username == username)
        ).first()
        if user and user.role != role:
            user.role = role
            session.add(user)
            session.commit()
    return user


def save_workflow_results(tenant_id, workflow_execution_id, workflow_results):
    with Session(engine) as session:
        workflow_execution = session.exec(
            select(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.id == workflow_execution_id)
        ).one()

        workflow_execution.results = workflow_results
        session.commit()


def get_workflow_by_name(tenant_id, workflow_name):
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.name == workflow_name)
            .where(Workflow.is_deleted == False)
        ).first()

        return workflow


def get_previous_execution_id(tenant_id, workflow_id, workflow_execution_id):
    with Session(engine) as session:
        previous_execution = session.exec(
            select(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .where(WorkflowExecution.id != workflow_execution_id)
            .order_by(WorkflowExecution.started.desc())
            .limit(1)
        ).first()
        if previous_execution:
            return previous_execution
        else:
            return None


def create_rule(
    tenant_id,
    name,
    timeframe,
    timeunit,
    definition,
    definition_cel,
    created_by,
    grouping_criteria=None,
    group_description=None,
    require_approve=False,
    resolve_on=ResolveOn.NEVER.value,
):
    grouping_criteria = grouping_criteria or []
    with Session(engine) as session:
        rule = Rule(
            tenant_id=tenant_id,
            name=name,
            timeframe=timeframe,
            timeunit=timeunit,
            definition=definition,
            definition_cel=definition_cel,
            created_by=created_by,
            creation_time=datetime.utcnow(),
            grouping_criteria=grouping_criteria,
            group_description=group_description,
            require_approve=require_approve,
            resolve_on=resolve_on,
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule


def update_rule(
    tenant_id,
    rule_id,
    name,
    timeframe,
    timeunit,
    definition,
    definition_cel,
    updated_by,
    grouping_criteria,
    require_approve,
    resolve_on,
):
    with Session(engine) as session:
        rule = session.exec(
            select(Rule).where(Rule.tenant_id == tenant_id).where(Rule.id == rule_id)
        ).first()

        if rule:
            rule.name = name
            rule.timeframe = timeframe
            rule.timeunit = timeunit
            rule.definition = definition
            rule.definition_cel = definition_cel
            rule.grouping_criteria = grouping_criteria
            rule.require_approve = require_approve
            rule.updated_by = updated_by
            rule.update_time = datetime.utcnow()
            rule.resolve_on = resolve_on
            session.commit()
            session.refresh(rule)
            return rule
        else:
            return None


def get_rules(tenant_id, ids=None):
    with Session(engine) as session:
        # Start building the query
        query = select(Rule).where(Rule.tenant_id == tenant_id)

        # Apply additional filters if ids are provided
        if ids is not None:
            query = query.where(Rule.id.in_(ids))

        # Execute the query
        rules = session.exec(query).all()
        return rules


def create_alert(tenant_id, provider_type, provider_id, event, fingerprint):
    with Session(engine) as session:
        alert = Alert(
            tenant_id=tenant_id,
            provider_type=provider_type,
            provider_id=provider_id,
            event=event,
            fingerprint=fingerprint,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert


def delete_rule(tenant_id, rule_id):
    with Session(engine) as session:
        rule = session.exec(
            select(Rule).where(Rule.tenant_id == tenant_id).where(Rule.id == rule_id)
        ).first()

        if rule:
            session.delete(rule)
            session.commit()
            return True
        return False


def get_incident_for_grouping_rule(
    tenant_id, rule, timeframe, rule_fingerprint, session: Optional[Session] = None
) -> Incident:
    # checks if incident with the incident criteria exists, if not it creates it
    #   and then assign the alert to the incident
    with existed_or_new_session(session) as session:
        incident = session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.rule_id == rule.id)
            .where(Incident.rule_fingerprint == rule_fingerprint)
            .where(Incident.status != IncidentStatus.RESOLVED.value)
            .order_by(Incident.creation_time.desc())
        ).first()

        # if the last alert in the incident is older than the timeframe, create a new incident
        is_incident_expired = False
        if incident and incident.alerts:
            is_incident_expired = max(
                alert.timestamp for alert in incident.alerts
            ) < datetime.utcnow() - timedelta(seconds=timeframe)

        # if there is no incident with the rule_fingerprint, create it or existed is already expired
        if not incident or is_incident_expired:
            # Create and add a new incident if it doesn't exist
            incident = Incident(
                tenant_id=tenant_id,
                user_generated_name=f"{rule.name}",
                rule_id=rule.id,
                rule_fingerprint=rule_fingerprint,
                is_predicted=False,
                is_confirmed=not rule.require_approve,
            )
            session.add(incident)
            session.commit()
            session.refresh(incident)

    return incident


def get_rule(tenant_id, rule_id):
    with Session(engine) as session:
        rule = session.exec(
            select(Rule).where(Rule.tenant_id == tenant_id).where(Rule.id == rule_id)
        ).first()
    return rule


def get_rule_incidents_count_db(tenant_id):
    with Session(engine) as session:
        query = (
            session.query(Incident.rule_id, func.count(Incident.id))
            .select_from(Incident)
            .filter(Incident.tenant_id == tenant_id, col(Incident.rule_id).isnot(None))
            .group_by(Incident.rule_id)
        )
        return dict(query.all())


def get_rule_distribution(tenant_id, minute=False):
    """Returns hits per hour for each rule, optionally breaking down by groups if the rule has 'group by', limited to the last 7 days."""
    with Session(engine) as session:
        # Get the timestamp for 7 days ago
        seven_days_ago = datetime.utcnow() - timedelta(days=1)

        # Check the dialect
        if session.bind.dialect.name == "mysql":
            time_format = "%Y-%m-%d %H:%i" if minute else "%Y-%m-%d %H"
            timestamp_format = func.date_format(AlertToIncident.timestamp, time_format)
        elif session.bind.dialect.name == "postgresql":
            time_format = "YYYY-MM-DD HH:MI" if minute else "YYYY-MM-DD HH"
            timestamp_format = func.to_char(AlertToIncident.timestamp, time_format)
        elif session.bind.dialect.name == "sqlite":
            time_format = "%Y-%m-%d %H:%M" if minute else "%Y-%m-%d %H"
            timestamp_format = func.strftime(time_format, AlertToIncident.timestamp)
        else:
            raise ValueError("Unsupported database dialect")
        # Construct the query
        query = (
            session.query(
                Rule.id.label("rule_id"),
                Rule.name.label("rule_name"),
                Incident.id.label("group_id"),
                Incident.rule_fingerprint.label("rule_fingerprint"),
                timestamp_format.label("time"),
                func.count(AlertToIncident.alert_id).label("hits"),
            )
            .join(Incident, Rule.id == Incident.rule_id)
            .join(AlertToIncident, Incident.id == AlertToIncident.incident_id)
            .filter(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.timestamp >= seven_days_ago,
            )
            .filter(Rule.tenant_id == tenant_id)  # Filter by tenant_id
            .group_by(
                "rule_id", "rule_name", "incident_id", "rule_fingerprint", "time"
            )  # Adjusted here
            .order_by("time")
        )

        results = query.all()

        # Convert the results into a dictionary
        rule_distribution = {}
        for result in results:
            rule_id = result.rule_id
            rule_fingerprint = result.rule_fingerprint
            timestamp = result.time
            hits = result.hits

            if rule_id not in rule_distribution:
                rule_distribution[rule_id] = {}

            if rule_fingerprint not in rule_distribution[rule_id]:
                rule_distribution[rule_id][rule_fingerprint] = {}

            rule_distribution[rule_id][rule_fingerprint][timestamp] = hits

        return rule_distribution


def get_all_deduplication_rules(tenant_id):
    with Session(engine) as session:
        rules = session.exec(
            select(AlertDeduplicationRule).where(
                AlertDeduplicationRule.tenant_id == tenant_id
            )
        ).all()
    return rules


def get_custom_deduplication_rule(tenant_id, provider_id, provider_type):
    with Session(engine) as session:
        rule = session.exec(
            select(AlertDeduplicationRule)
            .where(AlertDeduplicationRule.tenant_id == tenant_id)
            .where(AlertDeduplicationRule.provider_id == provider_id)
            .where(AlertDeduplicationRule.provider_type == provider_type)
        ).first()
    return rule


def create_deduplication_rule(
    tenant_id: str,
    name: str,
    description: str,
    provider_id: str | None,
    provider_type: str,
    created_by: str,
    enabled: bool = True,
    fingerprint_fields: list[str] = [],
    full_deduplication: bool = False,
    ignore_fields: list[str] = [],
    priority: int = 0,
):
    with Session(engine) as session:
        new_rule = AlertDeduplicationRule(
            tenant_id=tenant_id,
            name=name,
            description=description,
            provider_id=provider_id,
            provider_type=provider_type,
            last_updated_by=created_by,  # on creation, last_updated_by is the same as created_by
            created_by=created_by,
            enabled=enabled,
            fingerprint_fields=fingerprint_fields,
            full_deduplication=full_deduplication,
            ignore_fields=ignore_fields,
            priority=priority,
        )
        session.add(new_rule)
        session.commit()
        session.refresh(new_rule)
    return new_rule


def update_deduplication_rule(
    rule_id: str,
    tenant_id: str,
    name: str,
    description: str,
    provider_id: str | None,
    provider_type: str,
    last_updated_by: str,
    enabled: bool = True,
    fingerprint_fields: list[str] = [],
    full_deduplication: bool = False,
    ignore_fields: list[str] = [],
    priority: int = 0,
):
    with Session(engine) as session:
        rule = session.exec(
            select(AlertDeduplicationRule)
            .where(AlertDeduplicationRule.id == rule_id)
            .where(AlertDeduplicationRule.tenant_id == tenant_id)
        ).first()
        if not rule:
            raise ValueError(f"No deduplication rule found with id {rule_id}")

        rule.name = name
        rule.description = description
        rule.provider_id = provider_id
        rule.provider_type = provider_type
        rule.last_updated_by = last_updated_by
        rule.enabled = enabled
        rule.fingerprint_fields = fingerprint_fields
        rule.full_deduplication = full_deduplication
        rule.ignore_fields = ignore_fields
        rule.priority = priority

        session.add(rule)
        session.commit()
        session.refresh(rule)
    return rule


def delete_deduplication_rule(rule_id: str, tenant_id: str) -> bool:
    with Session(engine) as session:
        rule = session.exec(
            select(AlertDeduplicationRule)
            .where(AlertDeduplicationRule.id == rule_id)
            .where(AlertDeduplicationRule.tenant_id == tenant_id)
        ).first()
        if not rule:
            return False

        session.delete(rule)
        session.commit()
    return True


def get_custom_deduplication_rules(tenant_id, provider_id, provider_type):
    with Session(engine) as session:
        rules = session.exec(
            select(AlertDeduplicationRule)
            .where(AlertDeduplicationRule.tenant_id == tenant_id)
            .where(AlertDeduplicationRule.provider_id == provider_id)
            .where(AlertDeduplicationRule.provider_type == provider_type)
        ).all()
    return rules


def create_deduplication_event(
    tenant_id, deduplication_rule_id, deduplication_type, provider_id, provider_type
):
    with Session(engine) as session:
        deduplication_event = AlertDeduplicationEvent(
            tenant_id=tenant_id,
            deduplication_rule_id=deduplication_rule_id,
            deduplication_type=deduplication_type,
            provider_id=provider_id,
            provider_type=provider_type,
            timestamp=datetime.utcnow(),
            date_hour=datetime.utcnow().replace(minute=0, second=0, microsecond=0),
        )
        session.add(deduplication_event)
        session.commit()


def get_all_alerts_by_providers(tenant_id):
    with Session(engine) as session:
        # Query to get the count of alerts per provider_id and provider_type
        query = (
            select(
                Alert.provider_id,
                Alert.provider_type,
                func.count(Alert.id).label("num_alerts"),
            )
            .where(Alert.tenant_id == tenant_id)
            .group_by(Alert.provider_id, Alert.provider_type)
        )

        results = session.exec(query).all()

        # Create a dictionary with the number of alerts for each provider
        stats = {}
        for result in results:
            provider_id = result.provider_id
            provider_type = result.provider_type
            num_alerts = result.num_alerts

            key = f"{provider_type}_{provider_id}"
            stats[key] = {
                "num_alerts": num_alerts,
            }

    return stats


def get_all_deduplication_stats(tenant_id):
    with Session(engine) as session:
        # Query to get all-time deduplication stats
        all_time_query = (
            select(
                AlertDeduplicationEvent.deduplication_rule_id,
                AlertDeduplicationEvent.provider_id,
                AlertDeduplicationEvent.provider_type,
                AlertDeduplicationEvent.deduplication_type,
                func.count(AlertDeduplicationEvent.id).label("dedup_count"),
            )
            .where(AlertDeduplicationEvent.tenant_id == tenant_id)
            .group_by(
                AlertDeduplicationEvent.deduplication_rule_id,
                AlertDeduplicationEvent.provider_id,
                AlertDeduplicationEvent.provider_type,
                AlertDeduplicationEvent.deduplication_type,
            )
        )

        all_time_results = session.exec(all_time_query).all()

        # Query to get alerts distribution in the last 24 hours
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        alerts_last_24_hours_query = (
            select(
                AlertDeduplicationEvent.deduplication_rule_id,
                AlertDeduplicationEvent.provider_id,
                AlertDeduplicationEvent.provider_type,
                AlertDeduplicationEvent.date_hour,
                func.count(AlertDeduplicationEvent.id).label("hourly_count"),
            )
            .where(AlertDeduplicationEvent.tenant_id == tenant_id)
            .where(AlertDeduplicationEvent.date_hour >= twenty_four_hours_ago)
            .group_by(
                AlertDeduplicationEvent.deduplication_rule_id,
                AlertDeduplicationEvent.provider_id,
                AlertDeduplicationEvent.provider_type,
                AlertDeduplicationEvent.date_hour,
            )
        )

        alerts_last_24_hours_results = session.exec(alerts_last_24_hours_query).all()

        # Create a dictionary with deduplication stats for each rule
        stats = {}
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        for result in all_time_results:
            provider_id = result.provider_id
            provider_type = result.provider_type
            dedup_count = result.dedup_count
            dedup_type = result.deduplication_type

            # alerts without provider_id and provider_type are considered as "keep"
            if not provider_type:
                provider_type = "keep"

            key = str(result.deduplication_rule_id)
            if key not in stats:
                # initialize the stats for the deduplication rule
                stats[key] = {
                    "full_dedup_count": 0,
                    "partial_dedup_count": 0,
                    "none_dedup_count": 0,
                    "alerts_last_24_hours": [
                        {"hour": (current_hour - timedelta(hours=i)).hour, "number": 0}
                        for i in range(0, 24)
                    ],
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                }

            if dedup_type == "full":
                stats[key]["full_dedup_count"] += dedup_count
            elif dedup_type == "partial":
                stats[key]["partial_dedup_count"] += dedup_count
            elif dedup_type == "none":
                stats[key]["none_dedup_count"] += dedup_count

        # Add alerts distribution from the last 24 hours
        for result in alerts_last_24_hours_results:
            provider_id = result.provider_id
            provider_type = result.provider_type
            date_hour = result.date_hour
            hourly_count = result.hourly_count
            key = str(result.deduplication_rule_id)

            if not provider_type:
                provider_type = "keep"

            if key in stats:
                hours_ago = int((current_hour - date_hour).total_seconds() / 3600)
                if 0 <= hours_ago < 24:
                    stats[key]["alerts_last_24_hours"][23 - hours_ago][
                        "number"
                    ] = hourly_count

    return stats


def get_last_alert_hash_by_fingerprint(tenant_id, fingerprint):
    # get the last alert for a given fingerprint
    # to check deduplication
    with Session(engine) as session:
        query = (
            select(Alert.alert_hash)
            .where(Alert.tenant_id == tenant_id)
            .where(Alert.fingerprint == fingerprint)
            .order_by(Alert.timestamp.desc())
            .limit(1)  # Add LIMIT 1 for MSSQL
        )

        alert_hash = session.exec(query).first()
    return alert_hash


def update_key_last_used(
    tenant_id: str,
    reference_id: str,
) -> str:
    """
    Updates API key last used.

    Args:
        session (Session): _description_
        tenant_id (str): _description_
        reference_id (str): _description_

    Returns:
        str: _description_
    """
    with Session(engine) as session:
        # Get API Key from database
        statement = (
            select(TenantApiKey)
            .where(TenantApiKey.reference_id == reference_id)
            .where(TenantApiKey.tenant_id == tenant_id)
        )

        tenant_api_key_entry = session.exec(statement).first()

        # Update last used
        if not tenant_api_key_entry:
            # shouldn't happen but somehow happened to specific tenant so logging it
            logger.error(
                "API key not found",
                extra={"tenant_id": tenant_id, "unique_api_key_id": reference_id},
            )
            return
        tenant_api_key_entry.last_used = datetime.utcnow()
        session.add(tenant_api_key_entry)
        session.commit()


def get_linked_providers(tenant_id: str) -> List[Tuple[str, str, datetime]]:
    with Session(engine) as session:
        providers = (
            session.query(
                Alert.provider_type,
                Alert.provider_id,
                func.max(Alert.timestamp).label("last_alert_timestamp"),
            )
            .outerjoin(Provider, Alert.provider_id == Provider.id)
            .filter(
                Alert.tenant_id == tenant_id,
                Alert.provider_type != "group",
                Provider.id
                == None,  # Filters for alerts with a provider_id not in Provider table
            )
            .group_by(Alert.provider_type, Alert.provider_id)
            .all()
        )

    return providers


def is_linked_provider(tenant_id: str, provider_id: str) -> bool:
    with Session(engine) as session:
        linked_provider = (
            session.query(Alert.provider_id)
            .outerjoin(Provider, Alert.provider_id == Provider.id)
            .filter(
                Alert.tenant_id == tenant_id,
                Alert.provider_type != "group",
                Alert.provider_id == provider_id,
                Provider.id == None,
            )
            .first()
        )

    return linked_provider is not None


def get_provider_distribution(
    tenant_id: str,
    aggregate_all: bool = False,
    timestamp_filter: TimeStampFilter = None,
) -> (
    list[dict[str, int | Any]]
    | dict[str, dict[str, datetime | list[dict[str, int]] | Any]]
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


def get_preset_by_name(tenant_id: str, preset_name: str) -> Preset:
    with Session(engine) as session:
        preset = session.exec(
            select(Preset)
            .where(Preset.tenant_id == tenant_id)
            .where(Preset.name == preset_name)
        ).first()
    return preset

def get_all_presets(tenant_id: str) -> List[Preset]:
    with Session(engine) as session:
        presets = (
            session.exec(select(Preset).where(Preset.tenant_id == tenant_id))
            .unique()
            .all()
        )
    return presets

# 
def get_db_and_static_presets_dtos(tenant_id: str) -> List[PresetDto]:
    presets = get_all_presets(tenant_id)
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


def get_tenants_configurations(only_with_config=False) -> List[Tenant]:
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
    alert_id: UUID | str,
    incident: Incident,
    tenant_id: str,
    session: Optional[Session] = None,
):
    return add_alerts_to_incident(tenant_id, incident, [alert_id], session=session)


def is_alert_assigned_to_incident(
    alert_id: UUID, incident_id: UUID, tenant_id: str
) -> bool:
    with Session(engine) as session:
        assigned = session.exec(
            select(AlertToIncident)
            .where(AlertToIncident.alert_id == alert_id)
            .where(AlertToIncident.incident_id == incident_id)
            .where(AlertToIncident.tenant_id == tenant_id)
            .where(AlertToIncident.deleted_at == NULL_FOR_DELETED_AT)
        ).first()
    return assigned is not None


def get_incidents(tenant_id) -> List[Incident]:
    with Session(engine) as session:
        incidents = session.exec(
            select(Incident)
            .options(selectinload(Incident.alerts))
            .where(Incident.tenant_id == tenant_id)
            .order_by(desc(Incident.creation_time))
        ).all()
    return incidents


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


def get_workflows_with_last_executions_v2(
    tenant_id: str, fetch_last_executions: int = 15
) -> list[dict]:
    if fetch_last_executions is not None and fetch_last_executions > 20:
        fetch_last_executions = 20

    # List first 1000 worflows and thier last executions in the last 7 days which are active)
    with Session(engine) as session:
        latest_executions_subquery = (
            select(
                WorkflowExecution.workflow_id,
                WorkflowExecution.started,
                WorkflowExecution.execution_time,
                WorkflowExecution.status,
                func.row_number()
                .over(
                    partition_by=WorkflowExecution.workflow_id,
                    order_by=desc(WorkflowExecution.started),
                )
                .label("row_num"),
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(
                WorkflowExecution.started
                >= datetime.now(tz=timezone.utc) - timedelta(days=7)
            )
            .cte("latest_executions_subquery")
        )

        workflows_with_last_executions_query = (
            select(
                Workflow,
                latest_executions_subquery.c.started,
                latest_executions_subquery.c.execution_time,
                latest_executions_subquery.c.status,
            )
            .outerjoin(
                latest_executions_subquery,
                and_(
                    Workflow.id == latest_executions_subquery.c.workflow_id,
                    latest_executions_subquery.c.row_num <= fetch_last_executions,
                ),
            )
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.is_deleted == False)
            .order_by(Workflow.id, desc(latest_executions_subquery.c.started))
            .limit(15000)
        ).distinct()

        result = session.execute(workflows_with_last_executions_query).all()

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
                .outerjoin(sources_join, True)
                .outerjoin(affected_services_join, True)
                .filter(Incident.tenant_id == tenant_id, Incident.is_confirmed == True)
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
                .outerjoin(sources_join, True)
                .outerjoin(affected_services_join, True)
                .filter(Incident.tenant_id == tenant_id, Incident.is_confirmed == True)
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
                .outerjoin(sources_join, True)
                .outerjoin(affected_services_join, True)
                .filter(Incident.tenant_id == tenant_id, Incident.is_confirmed == True)
            )

            results = session.exec(query).one_or_none()
            if not results:
                return {}

            return {
                "assignees": list(filter(bool, results.assignees)),
                "sources": list(filter(bool, results.sources)),
                "services": list(filter(bool, results.affected_services)),
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


def get_last_incidents(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_confirmed: bool = False,
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
        is_confirmed (bool): Return confirmed incidents or predictions
        upper_timestamp: datetime = None,
        lower_timestamp: datetime = None,
        is_confirmed (bool): filter incident candidates or real incidents
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
        ).filter(Incident.tenant_id == tenant_id, Incident.is_confirmed == is_confirmed)

        if allowed_incident_ids:
            query = query.filter(Incident.id.in_(allowed_incident_ids))

        if with_alerts:
            query = query.options(joinedload(Incident.alerts))

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

    return incidents, total_count


def get_incident_by_id(
    tenant_id: str, incident_id: str | UUID, with_alerts: bool = False
) -> Optional[Incident]:
    with Session(engine) as session:
        query = session.query(
            Incident,
        ).filter(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
        if with_alerts:
            query = query.options(joinedload(Incident.alerts))

    return query.first()


def create_incident_from_dto(
    tenant_id: str,
    incident_dto: IncidentDtoIn | IncidentDto,
    generated_from_ai: bool = False,
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
            "is_confirmed": True,  # confirmed by the user :)
        }

    elif issubclass(type(incident_dto), IncidentDto):
        # we will reach this block when incident is pulled from a provider
        incident_dict = incident_dto.to_db_incident().dict()

    else:
        # We'll reach this block when a user creates an incident
        incident_dict = incident_dto.dict()

    return create_incident_from_dict(tenant_id, incident_dict)


def create_incident_from_dict(
    tenant_id: str, incident_data: dict
) -> Optional[Incident]:
    is_predicted = incident_data.get("is_predicted", False)
    if "is_confirmed" not in incident_data:
        incident_data["is_confirmed"] = not is_predicted
    with Session(engine) as session:
        new_incident = Incident(**incident_data, tenant_id=tenant_id)
        session.add(new_incident)
        session.commit()
        session.refresh(new_incident)
        new_incident.alerts = []
    return new_incident


def update_incident_from_dto_by_id(
    tenant_id: str,
    incident_id: str,
    updated_incident_dto: IncidentDtoIn | IncidentDto,
    generated_by_ai: bool = False,
) -> Optional[Incident]:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
            .options(joinedload(Incident.alerts))
        ).first()

        if not incident:
            return None

        if issubclass(type(updated_incident_dto), IncidentDto):
            # We execute this when we update an incident received from the provider
            updated_data = updated_incident_dto.to_db_incident().dict()
        else:
            # When a user updates an Incident
            updated_data = updated_incident_dto.dict()

        for key, value in updated_data.items():
            # Update only if the new value is different from the current one
            if hasattr(incident, key) and getattr(incident, key) != value:
                if isinstance(value, Enum):
                    setattr(incident, key, value.value)

                else:
                    setattr(incident, key, value)

        if generated_by_ai:
            incident.generated_summary = updated_incident_dto.user_summary
        else:
            incident.user_summary = updated_incident_dto.user_summary

        session.commit()
        session.refresh(incident)

        return incident


def get_incident_by_fingerprint(tenant_id: str, fingerprint: str) -> Optional[Incident]:
    with Session(engine) as session:
        return session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id, Incident.fingerprint == fingerprint
            )
        ).one_or_none()


def delete_incident_by_id(
    tenant_id: str,
    incident_id: UUID,
) -> bool:
    with Session(engine) as session:
        incident = (
            session.query(Incident)
            .filter(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
            .first()
        )

        # Delete all associations with alerts:

        (
            session.query(AlertToIncident)
            .where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
            )
            .delete()
        )

        session.delete(incident)
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
) -> tuple[List[tuple[Alert, AlertToIncident]], int]:
    with existed_or_new_session(session) as session:

        last_fingerprints_subquery = (
            session.query(
                Alert.fingerprint, func.max(Alert.timestamp).label("max_timestamp")
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .filter(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident_id,
            )
            .group_by(Alert.fingerprint)
            .subquery()
        )

        query = (
            session.query(
                Alert,
                AlertToIncident,
            )
            .select_from(last_fingerprints_subquery)
            .outerjoin(
                Alert,
                and_(
                    last_fingerprints_subquery.c.fingerprint == Alert.fingerprint,
                    last_fingerprints_subquery.c.max_timestamp == Alert.timestamp,
                ),
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .filter(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident_id,
            )
            .order_by(col(Alert.timestamp).desc())
            .options(joinedload(Alert.alert_enrichment))
        )
        if not include_unlinked:
            query = query.filter(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
            )

    total_count = query.count()

    if limit is not None and offset is not None:
        query = query.limit(limit).offset(offset)

    return query.all(), total_count


def get_incident_alerts_by_incident_id(*args, **kwargs) -> tuple[List[Alert], int]:
    """
    Unpacking (List[(Alert, AlertToIncident)], int) to (List[Alert], int).
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


def get_all_same_alert_ids(
    tenant_id: str, alert_ids: List[str | UUID], session: Optional[Session] = None
):
    with existed_or_new_session(session) as session:
        fingerprints_subquery = (
            session.query(Alert.fingerprint)
            .where(Alert.tenant_id == tenant_id, col(Alert.id).in_(alert_ids))
            .subquery()
        )
        query = session.scalars(
            select(Alert.id).where(
                Alert.tenant_id == tenant_id,
                col(Alert.fingerprint).in_(fingerprints_subquery),
            )
        )
        return query.all()


def get_alerts_data_for_incident(
    tenant_id: str,
    alert_ids: List[str | UUID],
    existed_fingerprints: Optional[List[str]] = None,
    session: Optional[Session] = None,
) -> dict:
    """
    Function to prepare aggregated data for incidents from the given list of alert_ids
    Logic is wrapped to the inner function for better usability with an optional database session

    Args:
        tenant_id (str): The tenant ID to filter alerts
        alert_ids (list[str | UUID]): list of alert ids for aggregation
        session (Optional[Session]): The database session or None

    Returns: dict {sources: list[str], services: list[str], count: int}
    """
    existed_fingerprints = existed_fingerprints or []

    with existed_or_new_session(session) as session:

        fields = (
            get_json_extract_field(session, Alert.event, "service"),
            Alert.provider_type,
            Alert.fingerprint,
            get_json_extract_field(session, Alert.event, "severity"),
        )

        alerts_data = session.exec(
            select(*fields).where(
                Alert.tenant_id == tenant_id,
                col(Alert.id).in_(alert_ids),
            )
        ).all()

        sources = []
        services = []
        severities = []
        fingerprints = set()

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
            if fingerprint and fingerprint not in existed_fingerprints:
                fingerprints.add(fingerprint)

        return {
            "sources": set(sources),
            "services": set(services),
            "max_severity": max(severities),
            "count": len(fingerprints),
        }


def add_alerts_to_incident_by_incident_id(
    tenant_id: str,
    incident_id: str | UUID,
    alert_ids: List[UUID],
    is_created_by_ai: bool = False,
    session: Optional[Session] = None,
) -> Optional[Incident]:
    with existed_or_new_session(session) as session:
        query = select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
        incident = session.exec(query).first()

        if not incident:
            return None
        return add_alerts_to_incident(
            tenant_id, incident, alert_ids, is_created_by_ai, session
        )


def add_alerts_to_incident(
    tenant_id: str,
    incident: Incident,
    alert_ids: List[UUID],
    is_created_by_ai: bool = False,
    session: Optional[Session] = None,
    override_count: bool = False,
) -> Optional[Incident]:
    logger.info(
        f"Adding alerts to incident {incident.id} in database, total {len(alert_ids)} alerts",
        extra={"tags": {"tenant_id": tenant_id, "incident_id": incident.id}},
    )

    with existed_or_new_session(session) as session:

        with session.no_autoflush:
            all_alert_ids = get_all_same_alert_ids(tenant_id, alert_ids, session)

            # Use a set for faster membership checks
            existing_alert_ids = set(
                session.exec(
                    select(AlertToIncident.alert_id).where(
                        AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                        AlertToIncident.tenant_id == tenant_id,
                        AlertToIncident.incident_id == incident.id,
                        col(AlertToIncident.alert_id).in_(all_alert_ids),
                    )
                ).all()
            )
            existing_fingerprints = set(
                session.exec(
                    select(Alert.fingerprint)
                    .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
                    .where(
                        AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                        AlertToIncident.tenant_id == tenant_id,
                        AlertToIncident.incident_id == incident.id,
                    )
                ).all()
            )

            new_alert_ids = [
                alert_id
                for alert_id in all_alert_ids
                if alert_id not in existing_alert_ids
            ]

            if not new_alert_ids:
                return incident

            alerts_data_for_incident = get_alerts_data_for_incident(
                tenant_id, new_alert_ids, existing_fingerprints, session
            )

            incident.sources = list(
                set(incident.sources if incident.sources else [])
                | set(alerts_data_for_incident["sources"])
            )
            incident.affected_services = list(
                set(incident.affected_services if incident.affected_services else [])
                | set(alerts_data_for_incident["services"])
            )
            # If incident has alerts already, use the max severity between existing and new alerts, otherwise use the new alerts max severity
            incident.severity = (
                max(incident.severity, alerts_data_for_incident["max_severity"].order)
                if incident.alerts_count
                else alerts_data_for_incident["max_severity"].order
            )
            if not override_count:
                incident.alerts_count += alerts_data_for_incident["count"]
            else:
                incident.alerts_count = alerts_data_for_incident["count"]
            alert_to_incident_entries = [
                AlertToIncident(
                    alert_id=alert_id,
                    incident_id=incident.id,
                    tenant_id=tenant_id,
                    is_created_by_ai=is_created_by_ai,
                )
                for alert_id in new_alert_ids
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

            started_at, last_seen_at = session.exec(
                select(func.min(Alert.timestamp), func.max(Alert.timestamp))
                .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
                .where(
                    AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                    AlertToIncident.tenant_id == tenant_id,
                    AlertToIncident.incident_id == incident.id,
                )
            ).one()

            incident.start_time = started_at
            incident.last_seen_time = last_seen_at

            session.add(incident)
            session.commit()
            session.refresh(incident)
            return incident


def get_incident_unique_fingerprint_count(tenant_id: str, incident_id: str) -> int:
    with Session(engine) as session:
        return session.execute(
            select(func.count(1))
            .select_from(AlertToIncident)
            .join(Alert, AlertToIncident.alert_id == Alert.id)
            .where(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                Alert.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident_id,
            )
        ).scalar()


def get_last_alerts_for_incidents(
    incident_ids: List[str | UUID],
) -> Dict[str, List[Alert]]:
    with Session(engine) as session:
        query = (
            session.query(
                Alert,
                AlertToIncident.incident_id,
            )
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .filter(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.incident_id.in_(incident_ids),
            )
            .order_by(Alert.timestamp.desc())
        )

        alerts = query.all()

    incidents_alerts = defaultdict(list)
    for alert, incident_id in alerts:
        incidents_alerts[str(incident_id)].append(alert)

    return incidents_alerts


def remove_alerts_to_incident_by_incident_id(
    tenant_id: str, incident_id: str | UUID, alert_ids: List[UUID]
) -> Optional[int]:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        ).first()

        if not incident:
            return None

        all_alert_ids = get_all_same_alert_ids(tenant_id, alert_ids, session)

        # Removing alerts-to-incident relation for provided alerts_ids
        deleted = (
            session.query(AlertToIncident)
            .where(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
                col(AlertToIncident.alert_id).in_(all_alert_ids),
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
            tenant_id, all_alert_ids, session=session
        )

        service_field = get_json_extract_field(session, Alert.event, "service")

        # checking if services of removed alerts are still presented in alerts
        # which still assigned with the incident
        existed_services_query = (
            select(func.distinct(service_field))
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .filter(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.incident_id == incident_id,
                service_field.in_(alerts_data_for_incident["services"]),
            )
        )
        services_existed = session.exec(existed_services_query)

        # checking if sources (providers) of removed alerts are still presented in alerts
        # which still assigned with the incident
        existed_sources_query = (
            select(col(Alert.provider_type).distinct())
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .filter(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.incident_id == incident_id,
                col(Alert.provider_type).in_(alerts_data_for_incident["sources"]),
            )
        )
        sources_existed = session.exec(existed_sources_query)

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

        started_at, last_seen_at = session.exec(
            select(func.min(Alert.timestamp), func.max(Alert.timestamp))
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
            )
        ).one()

        # filtering removed entities from affected services and sources in the incident
        incident.affected_services = [
            service
            for service in incident.affected_services
            if service not in services_to_remove
        ]
        incident.sources = [
            source for source in incident.sources if source not in sources_to_remove
        ]

        incident.alerts_count -= alerts_data_for_incident["count"]
        incident.severity = alerts_data_for_incident["max_severity"].order
        incident.start_time = started_at
        incident.last_seen_time = last_seen_at

        session.add(incident)
        session.commit()

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
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id, Incident.id == destination_incident_id
            )
            .options(joinedload(Incident.alerts))
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

        merged_incident_ids = []
        skipped_incident_ids = []
        failed_incident_ids = []
        for source_incident in source_incidents:
            source_incident_alerts_ids = [alert.id for alert in source_incident.alerts]
            if not source_incident_alerts_ids:
                logger.info(f"Source incident {source_incident.id} doesn't have alerts")
                skipped_incident_ids.append(source_incident.id)
                continue
            source_incident.merged_into_incident_id = destination_incident.id
            source_incident.merged_at = datetime.now(tz=timezone.utc)
            source_incident.status = IncidentStatus.MERGED.value
            source_incident.merged_by = merged_by
            try:
                remove_alerts_to_incident_by_incident_id(
                    tenant_id,
                    source_incident.id,
                    [alert.id for alert in source_incident.alerts],
                )
            except OperationalError as e:
                logger.error(
                    f"Error removing alerts to incident {source_incident.id}: {e}"
                )
            try:
                add_alerts_to_incident(
                    tenant_id,
                    destination_incident,
                    source_incident_alerts_ids,
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
        return merged_incident_ids, skipped_incident_ids, failed_incident_ids


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
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
                Incident.is_confirmed == expression.false(),
            )
            .options(joinedload(Incident.alerts))
        ).first()

        if not incident:
            return None

        session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
            Incident.is_confirmed == expression.false(),
        ).update(
            {
                "is_confirmed": True,
            }
        )

        session.commit()
        session.refresh(incident)

        return incident


def write_pmi_matrix_to_temp_file(
    tenant_id: str, pmi_matrix: np.array, fingerprints: List, temp_dir: str
) -> bool:
    np.savez(
        f"{temp_dir}/pmi_matrix.npz", pmi_matrix=pmi_matrix, fingerprints=fingerprints
    )
    return True


def get_pmi_values_from_temp_file(temp_dir: str) -> Tuple[np.array, Dict[str, int]]:
    npzfile = np.load(f"{temp_dir}/pmi_matrix.npz", allow_pickle=True)
    pmi_matrix = npzfile["pmi_matrix"]
    fingerprints = npzfile["fingerprints"]

    fingerint2idx = {fingerprint: i for i, fingerprint in enumerate(fingerprints)}

    return pmi_matrix, fingerint2idx


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


def get_topology_data_by_dynamic_matcher(
    tenant_id: str, matchers_value: dict[str, str]
) -> TopologyService | None:
    with Session(engine) as session:
        query = select(TopologyService).where(TopologyService.tenant_id == tenant_id)
        for matcher in matchers_value:
            query = query.where(
                getattr(TopologyService, matcher) == matchers_value[matcher]
            )
    return session.exec(query).first()


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
):
    with existed_or_new_session(session) as session:
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

        except IntegrityError:
            # Handle any potential race conditions
            session.rollback()


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
        updated = session.execute(stmt)
        session.commit()
        return updated.rowcount > 0


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
                Alert, WorkflowToAlertExecution.alert_fingerprint == Alert.fingerprint
            )
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .where(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.incident_id == incident_id,
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


def is_all_incident_alerts_resolved(
    incident: Incident, session: Optional[Session] = None
) -> bool:

    if incident.alerts_count == 0:
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
            .select_from(Alert)
            .outerjoin(
                AlertEnrichment, Alert.fingerprint == AlertEnrichment.alert_fingerprint
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .where(
                AlertToIncident.deleted_at == NULL_FOR_DELETED_AT,
                AlertToIncident.incident_id == incident.id,
            )
            .group_by(Alert.fingerprint)
            .having(func.max(Alert.timestamp))
        ).subquery()

        not_resolved_exists = session.query(
            exists(
                select(
                    subquery.c.enriched_status,
                    subquery.c.status,
                )
                .select_from(subquery)
                .where(
                    or_(
                        subquery.c.enriched_status != AlertStatus.RESOLVED.value,
                        and_(
                            subquery.c.enriched_status.is_(None),
                            subquery.c.status != AlertStatus.RESOLVED.value,
                        ),
                    )
                )
            )
        ).scalar()

        return not not_resolved_exists


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
                AlertEnrichment, Alert.fingerprint == AlertEnrichment.alert_fingerprint
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .where(AlertToIncident.incident_id == incident.id)
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
                [
                    (
                        func.json_extract(Alert.event, f"$.{field}").isnot(None)
                        & (func.json_extract(Alert.event, f"$.{field}") != False),
                        1,
                    )
                ],
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
                    case([(AlertToIncident.alert_id.isnot(None), 1)], else_=0)
                ).label("correlated_alerts"),
                *dynamic_field_sums,
            )
            .outerjoin(AlertToIncident, Alert.id == AlertToIncident.alert_id)
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

    return {
        f"{row.provider_id}_{row.provider_type}": {
            "total_alerts": row.total_alerts,
            "correlated_alerts": row.correlated_alerts,
            "provider_type": row.provider_type,
            **{
                f"{field}_count": getattr(row, f"{field}_count") for field in fields
            },  # Add field-specific counts
        }
        for row in results
    }


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

def get_or_creat_posthog_instance_id(
        session: Optional[Session] = None
    ):
        POSTHOG_INSTANCE_ID_KEY = "posthog_instance_id"
        with Session(engine) as session:
            system = session.exec(select(System).where(System.name == POSTHOG_INSTANCE_ID_KEY)).first()
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
        
def get_activity_report(
        session: Optional[Session] = None   
    ):
    from keep.api.models.db.user import User

    last_24_hours = datetime.utcnow() - timedelta(hours=24)
    activity_report = {}
    with Session(engine) as session:
        activity_report['tenants_count'] = session.query(Tenant).count()
        activity_report['providers_count'] = session.query(Provider).count()
        activity_report['users_count'] = session.query(User).count()
        activity_report['last_24_hours_incidents_count'] = session.query(Incident).filter(
            Incident.creation_time >= last_24_hours).count()
        activity_report['last_24_hours_alerts_count'] = session.query(Alert).filter(
            Alert.timestamp >= last_24_hours).count()
        activity_report['last_24_hours_rules_created'] = session.query(Rule).filter(
            Rule.creation_time >= last_24_hours).count()
        activity_report['last_24_hours_workflows_created'] = session.query(Workflow).filter(
            Workflow.creation_time >= last_24_hours).count()
        activity_report['last_24_hours_workflows_executed'] = session.query(WorkflowExecution).filter(
            WorkflowExecution.started >= last_24_hours).count()
        
    return activity_report
