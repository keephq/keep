"""
Keep main database module.

This module contains the CRUD database functions for Keep.
"""

import hashlib
import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple, Union
from uuid import uuid4

import pandas as pd
import validators
from dotenv import find_dotenv, load_dotenv
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import and_, desc, null, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload, selectinload, subqueryload
from sqlalchemy.sql import expression
from sqlmodel import Session, col, or_, select

from keep.api.core.db_utils import create_db_engine, get_json_extract_field

# This import is required to create the tables
from keep.api.models.alert import IncidentDtoIn
from keep.api.models.db.action import Action
from keep.api.models.db.alert import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.dashboard import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.extraction import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.mapping import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.preset import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.provider import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.rule import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.statistics import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.tenant import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.topology import *  # pylint: disable=unused-wildcard-import
from keep.api.models.db.workflow import *  # pylint: disable=unused-wildcard-import

logger = logging.getLogger(__name__)


# this is a workaround for gunicorn to load the env vars
#   becuase somehow in gunicorn it doesn't load the .env file
load_dotenv(find_dotenv())


engine = create_db_engine()
SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)


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
            if fingerprint:
                workflow_to_alert_execution = WorkflowToAlertExecution(
                    workflow_execution_id=execution_id,
                    alert_fingerprint=fingerprint,
                    event_id=event_id,
                )
                session.add(workflow_to_alert_execution)
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
                workflow_raw=workflow_raw,
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


def get_workflow_executions(tenant_id, workflow_id, limit=50):
    with Session(engine) as session:
        workflow_executions = session.exec(
            select(
                WorkflowExecution.id,
                WorkflowExecution.workflow_id,
                WorkflowExecution.started,
                WorkflowExecution.status,
                WorkflowExecution.triggered_by,
                WorkflowExecution.execution_time,
                WorkflowExecution.error,
            )
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .where(
                WorkflowExecution.started
                >= datetime.now(tz=timezone.utc) - timedelta(days=7)
            )
            .order_by(WorkflowExecution.started.desc())
            .limit(limit)
        ).all()
    return workflow_executions


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


def _enrich_alert(
    session,
    tenant_id,
    fingerprint,
    enrichments,
    action_type: AlertActionType,
    action_callee: str,
    action_description: str,
    force=False,
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
    return alert_enrichment


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
    if refresh:
        try:
            session.refresh(alert_enrichment)
        except Exception:
            logger.exception(
                "Failed to refresh enrichment",
                extra={"tenant_id": tenant_id, "fingerprint": fingerprint},
            )
    return alert_enrichment


def get_alerts_with_filters(
    tenant_id, provider_id=None, filters=None, time_delta=1
) -> list[Alert]:
    with Session(engine) as session:
        # Create the query
        query = session.query(Alert)

        # Apply subqueryload to force-load the alert_enrichment relationship
        query = query.options(subqueryload(Alert.alert_enrichment))

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

        # Order by timestamp in descending order and limit the results
        query = query.order_by(Alert.timestamp.desc()).limit(limit)

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
) -> list[Alert]:
    """
    Get the last alert for each fingerprint along with the first time the alert was triggered.

    Args:
        tenant_id (_type_): The tenant_id to filter the alerts by.
        provider_id (_type_, optional): The provider id to filter by. Defaults to None.

    Returns:
        List[Alert]: A list of Alert objects including the first time the alert was triggered.
    """
    with Session(engine) as session:
        # Subquery that selects the max and min timestamp for each fingerprint.
        subquery = (
            session.query(
                Alert.fingerprint,
                func.max(Alert.timestamp).label("max_timestamp"),
                func.min(Alert.timestamp).label(
                    "min_timestamp"
                ),  # Include minimum timestamp
            )
            .filter(Alert.tenant_id == tenant_id)
            .group_by(Alert.fingerprint)
            .subquery()
        )
        # if timeframe is provided, filter the alerts by the timeframe
        if timeframe:
            subquery = (
                session.query(subquery)
                .filter(
                    subquery.c.max_timestamp
                    >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
                )
                .subquery()
            )

        filter_conditions = []

        if upper_timestamp is not None:
            filter_conditions.append(subquery.c.max_timestamp < upper_timestamp)

        if lower_timestamp is not None:
            filter_conditions.append(subquery.c.max_timestamp >= lower_timestamp)

        # Apply the filter conditions
        if filter_conditions:
            subquery = (
                session.query(subquery)
                .filter(*filter_conditions)  # Unpack and apply all conditions
                .subquery()
            )
        # Main query joins the subquery to select alerts with their first and last occurrence.
        query = (
            session.query(
                Alert,
                subquery.c.min_timestamp.label(
                    "startedAt"
                ),  # Include "startedAt" in the selected columns
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

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        if timeframe:
            query = query.filter(
                subquery.c.max_timestamp
                >= datetime.now(tz=timezone.utc) - timedelta(days=timeframe)
            )

        # Order by timestamp in descending order and limit the results
        query = query.order_by(desc(Alert.timestamp)).limit(limit)
        # Execute the query
        alerts_with_start = query.all()
        # Convert result to list of Alert objects and include "startedAt" information if needed
        alerts = []
        for alert, startedAt in alerts_with_start:
            alert.event["startedAt"] = str(startedAt)
            alert.event["event_id"] = str(alert.id)
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


def get_users():
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.api.models.db.user import User

    with Session(engine) as session:
        users = session.exec(
            select(User).where(User.tenant_id == SINGLE_TENANT_UUID)
        ).all()
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


def save_workflow_results(tenant_id, workflow_execution_id, workflow_results):
    with Session(engine) as session:
        workflow_execution = session.exec(
            select(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
            .where(WorkflowExecution.id == workflow_execution_id)
        ).one()

        workflow_execution.results = workflow_results
        session.commit()


def get_workflow_id_by_name(tenant_id, workflow_name):
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.name == workflow_name)
            .where(Workflow.is_deleted == False)
        ).first()

        if workflow:
            return workflow.id


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
    definition,
    definition_cel,
    created_by,
    grouping_criteria=None,
    group_description=None,
    require_approve=False,
):
    grouping_criteria = grouping_criteria or []
    with Session(engine) as session:
        rule = Rule(
            tenant_id=tenant_id,
            name=name,
            timeframe=timeframe,
            definition=definition,
            definition_cel=definition_cel,
            created_by=created_by,
            creation_time=datetime.utcnow(),
            grouping_criteria=grouping_criteria,
            group_description=group_description,
            require_approve=require_approve,
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
    definition,
    definition_cel,
    updated_by,
    grouping_criteria,
    require_approve,
):
    with Session(engine) as session:
        rule = session.exec(
            select(Rule).where(Rule.tenant_id == tenant_id).where(Rule.id == rule_id)
        ).first()

        if rule:
            rule.name = name
            rule.timeframe = timeframe
            rule.definition = definition
            rule.definition_cel = definition_cel
            rule.grouping_criteria = grouping_criteria
            rule.require_approve = require_approve
            rule.updated_by = updated_by
            rule.update_time = datetime.utcnow()
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
    tenant_id, rule, timeframe, rule_fingerprint
) -> Incident:
    # checks if incident with the incident criteria exists, if not it creates it
    #   and then assign the alert to the incident
    with Session(engine) as session:
        incident = session.exec(
            select(Incident)
            .options(joinedload(Incident.alerts))
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.rule_id == rule.id)
            .where(Incident.rule_fingerprint == rule_fingerprint)
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
                name=f"Incident generated by rule {rule.name}",
                rule_id=rule.id,
                rule_fingerprint=rule_fingerprint,
                is_predicted=False,
                is_confirmed=not rule.require_approve,
            )
            session.add(incident)
            session.commit()

            # Re-query the incident with joinedload to set up future automatic loading of alerts
            incident = session.exec(
                select(Incident)
                .options(joinedload(Incident.alerts))
                .where(Incident.id == incident.id)
            ).first()

    return incident


def get_rule(tenant_id, rule_id):
    with Session(engine) as session:
        rule = session.exec(
            select(Rule).where(Rule.tenant_id == tenant_id).where(Rule.id == rule_id)
        ).first()
    return rule


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
            .filter(AlertToIncident.timestamp >= seven_days_ago)
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


def get_all_filters(tenant_id):
    with Session(engine) as session:
        filters = session.exec(
            select(AlertDeduplicationFilter).where(
                AlertDeduplicationFilter.tenant_id == tenant_id
            )
        ).all()
    return filters


def get_last_alert_hash_by_fingerprint(tenant_id, fingerprint):
    # get the last alert for a given fingerprint
    # to check deduplication
    with Session(engine) as session:
        alert_hash = session.exec(
            select(Alert.alert_hash)
            .where(Alert.tenant_id == tenant_id)
            .where(Alert.fingerprint == fingerprint)
            .order_by(Alert.timestamp.desc())
        ).first()
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
                extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
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


def get_provider_distribution(tenant_id: str) -> dict:
    """Returns hits per hour and the last alert timestamp for each provider, limited to the last 24 hours."""
    with Session(engine) as session:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        time_format = "%Y-%m-%d %H"

        if session.bind.dialect.name == "mysql":
            timestamp_format = func.date_format(Alert.timestamp, time_format)
        elif session.bind.dialect.name == "postgresql":
            # PostgreSQL requires a different syntax for the timestamp format
            # cf: https://www.postgresql.org/docs/current/functions-formatting.html#FUNCTIONS-FORMATTING
            timestamp_format = func.to_char(Alert.timestamp, "YYYY-MM-DD HH")
        elif session.bind.dialect.name == "sqlite":
            timestamp_format = func.strftime(time_format, Alert.timestamp)

        # Adjusted query to include max timestamp
        query = (
            session.query(
                Alert.provider_id,
                Alert.provider_type,
                timestamp_format.label("time"),
                func.count().label("hits"),
                func.max(Alert.timestamp).label(
                    "last_alert_timestamp"
                ),  # Include max timestamp
            )
            .filter(
                Alert.tenant_id == tenant_id,
                Alert.timestamp >= twenty_four_hours_ago,
            )
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
                    "last_alert_received": last_alert_timestamp,  # Initialize with the first seen timestamp
                }
            else:
                # Update the last alert timestamp if the current one is more recent
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


def get_presets(tenant_id: str, email) -> List[Dict[str, Any]]:
    with Session(engine) as session:
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


def assign_alert_to_incident(alert_id: UUID | str, incident_id: UUID, tenant_id: str):
    return add_alerts_to_incident_by_incident_id(tenant_id, incident_id, [alert_id])


def is_alert_assigned_to_incident(
    alert_id: UUID, incident_id: UUID, tenant_id: str
) -> bool:
    with Session(engine) as session:
        assigned = session.exec(
            select(AlertToIncident)
            .where(AlertToIncident.alert_id == alert_id)
            .where(AlertToIncident.incident_id == incident_id)
            .where(AlertToIncident.tenant_id == tenant_id)
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
    tenant_id: str, fingerprint: str, limit: int = 50
) -> List[AlertAudit]:
    with Session(engine) as session:
        audit = session.exec(
            select(AlertAudit)
            .where(AlertAudit.tenant_id == tenant_id)
            .where(AlertAudit.fingerprint == fingerprint)
            .order_by(desc(AlertAudit.timestamp))
            .limit(limit)
        ).all()
    return audit


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


def get_last_incidents(
    tenant_id: str,
    limit: int = 25,
    offset: int = 0,
    timeframe: int = None,
    upper_timestamp: datetime = None,
    lower_timestamp: datetime = None,
    is_confirmed: bool = False,
) -> Tuple[list[Incident], int]:
    """
    Get the last incidents and total amount of incidents.

    Args:
        tenant_id (str): The tenant_id to filter the incidents by.
        limit (int): Amount of objects to return
        offset (int): Current offset for
        timeframe (int|null): Return incidents only for the last <N> days
        is_confirmed (bool): Return confirmed incidents or predictions

    Returns:
        List[Incident]: A list of Incident objects.
    """
    with Session(engine) as session:
        query = (
            session.query(
                Incident,
            )
            .options(joinedload(Incident.alerts))
            .filter(
                Incident.tenant_id == tenant_id, Incident.is_confirmed == is_confirmed
            )
            .order_by(desc(Incident.creation_time))
        )

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

        total_count = query.count()

        # Order by start_time in descending order and limit the results
        query = query.order_by(desc(Incident.start_time)).limit(limit).offset(offset)
        # Execute the query
        incidents = query.all()

    return incidents, total_count


def get_incident_by_id(tenant_id: str, incident_id: str | UUID) -> Optional[Incident]:
    with Session(engine) as session:
        query = session.query(
            Incident,
        ).filter(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )

    return query.first()


def create_incident_from_dto(
    tenant_id: str, incident_dto: IncidentDtoIn
) -> Optional[Incident]:
    return create_incident_from_dict(tenant_id, incident_dto.dict())


def create_incident_from_dict(
    tenant_id: str, incident_data: dict
) -> Optional[Incident]:
    is_predicted = incident_data.get("is_predicted", False)
    with Session(engine) as session:
        new_incident = Incident(
            **incident_data, tenant_id=tenant_id, is_confirmed=not is_predicted
        )
        session.add(new_incident)
        session.commit()
        session.refresh(new_incident)
        new_incident.alerts = []
    return new_incident


def update_incident_from_dto_by_id(
    tenant_id: str,
    incident_id: str,
    updated_incident_dto: IncidentDtoIn,
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

        session.query(Incident).filter(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        ).update(
            {
                "name": updated_incident_dto.name,
                "user_summary": updated_incident_dto.user_summary,
                "assignee": updated_incident_dto.assignee,
            }
        )

        session.commit()
        session.refresh(incident)

        return incident


def delete_incident_by_id(
    tenant_id: str,
    incident_id: str,
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


def get_incident_alerts_by_incident_id(
    tenant_id: str, incident_id: str, limit: int, offset: int
) -> (List[Alert], int):
    with Session(engine) as session:
        query = (
            session.query(
                Alert,
            )
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .join(Incident, AlertToIncident.incident_id == Incident.id)
            .filter(
                AlertToIncident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
            .order_by(col(Alert.timestamp).desc())
        )

    total_count = query.count()

    return query.limit(limit).offset(offset).all(), total_count


def get_alerts_data_for_incident(
    alert_ids: list[str | UUID], session: Optional[Session] = None
) -> dict:
    """
    Function to prepare aggregated data for incidents from the given list of alert_ids
    Logic is wrapped to the inner function for better usability with an optional database session

    Args:
        alert_ids (list[str | UUID]): list of alert ids for aggregation
        session (Optional[Session]): The database session or None

    Returns: dict {sources: list[str], services: list[str], count: int}
    """

    def inner(db_session: Session):

        fields = (
            get_json_extract_field(session, Alert.event, "service"),
            Alert.provider_type,
            get_json_extract_field(session, Alert.event, "severity"),
        )

        alerts_data = db_session.exec(
            select(*fields).where(
                col(Alert.id).in_(alert_ids),
            )
        ).all()

        sources = []
        services = []
        severities = []

        for service, source, severity in alerts_data:
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
            "max_severity": max(severities),
            "count": len(alerts_data),
        }

    # Ensure that we have a session to execute the query. If not - make new one
    if not session:
        with Session(engine) as session:
            return inner(session)
    return inner(session)


def add_alerts_to_incident_by_incident_id(
    tenant_id: str, incident_id: str | UUID, alert_ids: List[UUID]
) -> Optional[Incident]:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.id == incident_id,
            )
        ).first()

        if not incident:
            return None

        existed_alert_ids = session.exec(
            select(AlertToIncident.alert_id).where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
                col(AlertToIncident.alert_id).in_(alert_ids),
            )
        ).all()

        new_alert_ids = [
            alert_id for alert_id in alert_ids if alert_id not in existed_alert_ids
        ]

        if not new_alert_ids:
            return incident

        alerts_data_for_incident = get_alerts_data_for_incident(new_alert_ids, session)

        incident.sources = list(
            set(incident.sources) | set(alerts_data_for_incident["sources"])
        )
        incident.affected_services = list(
            set(incident.affected_services) | set(alerts_data_for_incident["services"])
        )
        incident.alerts_count += alerts_data_for_incident["count"]

        alert_to_incident_entries = [
            AlertToIncident(
                alert_id=alert_id, incident_id=incident.id, tenant_id=tenant_id
            )
            for alert_id in new_alert_ids
        ]

        session.bulk_save_objects(alert_to_incident_entries)

        started_at, last_seen_at = session.exec(
            select(func.min(Alert.timestamp), func.max(Alert.timestamp))
            .join(AlertToIncident, AlertToIncident.alert_id == Alert.id)
            .where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
            )
        ).one()
        incident.start_time = started_at
        incident.last_seen_time = last_seen_at

        incident.severity = alerts_data_for_incident["max_severity"].order

        session.add(incident)
        session.commit()
        session.refresh(incident)
        return incident


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

        # Removing alerts-to-incident relation for provided alerts_ids
        deleted = (
            session.query(AlertToIncident)
            .where(
                AlertToIncident.tenant_id == tenant_id,
                AlertToIncident.incident_id == incident.id,
                col(AlertToIncident.alert_id).in_(alert_ids),
            )
            .delete()
        )
        session.commit()

        # Getting aggregated data for incidents for alerts which just was removed
        alerts_data_for_incident = get_alerts_data_for_incident(alert_ids, session)

        service_field = get_json_extract_field(session, Alert.event, "service")

        # checking if services of removed alerts are still presented in alerts
        # which still assigned with the incident
        services_existed = session.exec(
            session.query(func.distinct(service_field))
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .filter(
                AlertToIncident.incident_id == incident_id,
                service_field.in_(alerts_data_for_incident["services"]),
            )
        ).scalars()

        # checking if sources (providers) of removed alerts are still presented in alerts
        # which still assigned with the incident
        sources_existed = session.exec(
            session.query(col(Alert.provider_type).distinct())
            .join(AlertToIncident, Alert.id == AlertToIncident.alert_id)
            .filter(
                AlertToIncident.incident_id == incident_id,
                col(Alert.provider_type).in_(alerts_data_for_incident["sources"]),
            )
        ).scalars()

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
        incident.start_time = started_at
        incident.last_seen_time = last_seen_at

        session.add(incident)
        session.commit()

        return deleted


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


def write_pmi_matrix_to_db(tenant_id: str, pmi_matrix_df: pd.DataFrame) -> bool:
    # TODO: add handlers for sequential launches
    with Session(engine) as session:
        pmi_entries_to_update = 0
        pmi_entries_to_insert = []

        # Query for existing entries to differentiate between updates and inserts
        existing_entries = session.query(PMIMatrix).filter_by(tenant_id=tenant_id).all()
        existing_entries_dict = {
            (entry.fingerprint_i, entry.fingerprint_j): entry
            for entry in existing_entries
        }

        for fingerprint_i in pmi_matrix_df.index:
            for fingerprint_j in pmi_matrix_df.columns:
                if pmi_matrix_df.at[fingerprint_i, fingerprint_j] == -100:
                    continue

                pmi = float(pmi_matrix_df.at[fingerprint_i, fingerprint_j])

                pmi_entry = {
                    "tenant_id": tenant_id,
                    "fingerprint_i": fingerprint_i,
                    "fingerprint_j": fingerprint_j,
                    "pmi": pmi,
                }

                if (fingerprint_i, fingerprint_j) in existing_entries_dict:
                    existed_entry = existing_entries_dict[
                        (fingerprint_i, fingerprint_j)
                    ]
                    if existed_entry.pmi != pmi:
                        session.execute(
                            update(PMIMatrix)
                            .where(
                                PMIMatrix.fingerprint_i == fingerprint_i,
                                PMIMatrix.fingerprint_j == fingerprint_j,
                                PMIMatrix.tenant_id == tenant_id,
                            )
                            .values(pmi=pmi)
                        )
                        pmi_entries_to_update += 1
                else:
                    pmi_entries_to_insert.append(pmi_entry)

        if pmi_entries_to_insert:
            session.bulk_insert_mappings(PMIMatrix, pmi_entries_to_insert)

        logger.info(
            f"PMI matrix for tenant {tenant_id} updated. {pmi_entries_to_update} entries updated, {len(pmi_entries_to_insert)} entries inserted",
            extra={"tenant_id": tenant_id},
        )

        session.commit()

    return True


def get_pmi_value(
    tenant_id: str, fingerprint_i: str, fingerprint_j: str
) -> Optional[float]:
    with Session(engine) as session:
        pmi_entry = session.exec(
            select(PMIMatrix)
            .where(PMIMatrix.tenant_id == tenant_id)
            .where(PMIMatrix.fingerprint_i == fingerprint_i)
            .where(PMIMatrix.fingerprint_j == fingerprint_j)
        ).first()

    return pmi_entry.pmi if pmi_entry else None


def get_pmi_values(
    tenant_id: str, fingerprints: List[str]
) -> Dict[Tuple[str, str], Optional[float]]:
    with Session(engine) as session:
        pmi_entries = session.exec(
            select(PMIMatrix).where(PMIMatrix.tenant_id == tenant_id)
        ).all()

    pmi_values = {
        (entry.fingerprint_i, entry.fingerprint_j): entry.pmi for entry in pmi_entries
    }
    return pmi_values


def update_incident_summary(incident_id: UUID, summary: str) -> Incident:
    with Session(engine) as session:
        incident = session.exec(
            select(Incident).where(Incident.id == incident_id)
        ).first()

        if not incident:
            return None

        incident.generated_summary = summary
        session.commit()
        session.refresh(incident)

        return incident


# Fetch all topology data
def get_all_topology_data(
    tenant_id: str,
    provider_id: Optional[str] = None,
    service: Optional[str] = None,
    environment: Optional[str] = None,
) -> List[TopologyServiceDtoOut]:
    with Session(engine) as session:
        query = select(TopologyService).where(TopologyService.tenant_id == tenant_id)

        # @tb: let's filter by service only for now and take care of it when we handle multilpe
        # services and environments and cmdbs
        # the idea is that we show the service topology regardless of the underlying provider/env
        # if provider_id is not None and service is not None and environment is not None:
        if service is not None:
            query = query.where(
                TopologyService.service == service,
                # TopologyService.source_provider_id == provider_id,
                # TopologyService.environment == environment,
            )

            service_instance = session.exec(query).first()
            if not service_instance:
                return []

            services = session.exec(
                select(TopologyServiceDependency)
                .where(
                    TopologyServiceDependency.depends_on_service_id
                    == service_instance.id
                )
                .options(joinedload(TopologyServiceDependency.service))
            ).all()
            services = [service_instance, *[service.service for service in services]]
        else:
            # Fetch services for the tenant
            services = session.exec(query).all()

        service_dtos = [TopologyServiceDtoOut.from_orm(service) for service in services]

        return service_dtos


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
