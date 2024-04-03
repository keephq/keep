import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from uuid import uuid4

import pymysql
import validators
from dotenv import find_dotenv, load_dotenv
from google.cloud.sql.connector import Connector
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import and_, desc, func, null, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload, subqueryload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy_utils import create_database, database_exists
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.alert import AlertStatus
from keep.api.models.db.alert import *
from keep.api.models.db.mapping import *
from keep.api.models.db.preset import *
from keep.api.models.db.provider import *
from keep.api.models.db.rule import *
from keep.api.models.db.tenant import *
from keep.api.models.db.workflow import *

logger = logging.getLogger(__name__)


def __get_conn() -> pymysql.connections.Connection:
    """
    Creates a connection to the database when running in Cloud Run.

    Returns:
        pymysql.connections.Connection: The DB connection.
    """
    with Connector() as connector:
        conn = connector.connect(
            "keephq-sandbox:us-central1:keep",  # Todo: get from configuration
            "pymysql",
            user="keep-api",
            db="keepdb",
            enable_iam_auth=True,
        )
    return conn


def __get_conn_impersonate() -> pymysql.connections.Connection:
    """
    Creates a connection to the remote database when running locally.

    Returns:
        pymysql.connections.Connection: The DB connection.
    """
    from google.auth import default, impersonated_credentials
    from google.auth.transport.requests import Request

    # Get application default credentials
    creds, project = default()
    # Create impersonated credentials
    target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal="keep-api@keephq-sandbox.iam.gserviceaccount.com",
        target_scopes=target_scopes,
    )
    # Refresh the credentials to obtain an impersonated access token
    creds.refresh(Request())
    # Get the access token
    access_token = creds.token
    # Create a new MySQL connection with the obtained access token
    with Connector() as connector:
        conn = connector.connect(
            "keephq-sandbox:us-central1:keep",  # Todo: get from configuration
            "pymysql",
            user="keep-api",
            password=access_token,
            host="127.0.0.1",
            port=3306,
            database="keepdb",
        )
    return conn


# this is a workaround for gunicorn to load the env vars
#   becuase somehow in gunicorn it doesn't load the .env file
load_dotenv(find_dotenv())
db_connection_string = config("DATABASE_CONNECTION_STRING", default=None)
pool_size = config("DATABASE_POOL_SIZE", default=5, cast=int)

if RUNNING_IN_CLOUD_RUN:
    engine = create_engine(
        "mysql+pymysql://",
        creator=__get_conn,
    )
elif db_connection_string == "impersonate":
    engine = create_engine(
        "mysql+pymysql://",
        creator=__get_conn_impersonate,
    )
elif db_connection_string:
    try:
        logger.info(f"Creating a connection pool with size {pool_size}")
        engine = create_engine(db_connection_string, pool_size=pool_size)
    # SQLite does not support pool_size
    except TypeError:
        engine = create_engine(db_connection_string)
else:
    engine = create_engine(
        "sqlite:///./keep.db", connect_args={"check_same_thread": False}
    )

SQLAlchemyInstrumentor().instrument(enable_commenter=True, engine=engine)


def create_db_and_tables():
    """
    Creates the database and tables.
    """
    try:
        if not database_exists(engine.url):
            logger.info("Creating the database")
            create_database(engine.url)
            logger.info("Database created")
    # On Cloud Run, it fails to check if the database exists
    except Exception:
        logger.warning("Failed to create the database or detect if it exists.")
        pass

    # migrate the workflowtoexecution table
    with Session(engine) as session:
        try:
            logger.info("Migrating WorkflowToAlertExecution table")
            # get the foreign key constraint name
            results = session.exec(
                f"SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE  WHERE TABLE_SCHEMA = '{engine.url.database}'  AND TABLE_NAME = 'workflowtoalertexecution' AND COLUMN_NAME = 'alert_fingerprint';"
            )
            # now remove it
            for row in results:
                constraint_name = row["CONSTRAINT_NAME"]
                if constraint_name.startswith("workflowtoalertexecution"):
                    logger.info(f"Dropping constraint {constraint_name}")
                    session.exec(
                        f"ALTER TABLE workflowtoalertexecution DROP FOREIGN KEY {constraint_name};"
                    )
                    logger.info(f"Dropped constraint {constraint_name}")
            # also add grouping_criteria to the workflow table
            logger.info("Migrating Rule table")
            try:
                session.exec("ALTER TABLE rule ADD COLUMN grouping_criteria JSON;")
            except Exception as e:
                # that's ok
                if "Duplicate column name" in str(e):
                    pass
                # else, log
                else:
                    logger.exception("Failed to migrate rule table")
                    pass
            logger.info("Migrated Rule table")
            session.commit()
            logger.info("Migrated succesfully")
        except Exception:
            logger.exception("Failed to migrate table")
            pass
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Creates a database session.

    Yields:
        Session: A database session
    """
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_session"):
        with Session(engine) as session:
            yield session


def try_create_single_tenant(tenant_id: str) -> None:
    try:
        # if Keep is not multitenant, let's import the User table too:
        from keep.api.models.db.user import User

        create_db_and_tables()
    except Exception:
        pass
    with Session(engine) as session:
        try:
            # check if the tenant exist:
            tenant = session.exec(select(Tenant).where(Tenant.id == tenant_id)).first()
            if not tenant:
                # Do everything related with single tenant creation in here
                logger.info("Creating single tenant")
                session.add(Tenant(id=tenant_id, name="Single Tenant"))
            else:
                logger.info("Single tenant already exists")

            # now let's create the default user

            # check if at least one user exists:
            user = session.exec(select(User)).first()
            # if no users exist, let's create the default user
            if not user:
                default_username = os.environ.get("KEEP_DEFAULT_USERNAME", "keep")
                default_password = hashlib.sha256(
                    os.environ.get("KEEP_DEFAULT_PASSWORD", "keep").encode()
                ).hexdigest()
                default_user = User(
                    username=default_username,
                    password_hash=default_password,
                    role=AdminRole.get_name(),
                )
                session.add(default_user)
            # else, if the user want to force the refresh of the default user password
            elif os.environ.get("KEEP_FORCE_RESET_DEFAULT_PASSWORD", "false") == "true":
                # update the password of the default user
                default_password = hashlib.sha256(
                    os.environ.get("KEEP_DEFAULT_PASSWORD", "keep").encode()
                ).hexdigest()
                user.password_hash = default_password
            # commit the changes
            session.commit()
        except IntegrityError:
            # Tenant already exists
            pass
        except Exception:
            pass
    # New session since the previous might be in a bad state
    with Session(engine) as session:
        try:
            # TODO: remove this once we have a migration system
            logger.info("Migrating TenantApiKey table")
            session.exec(
                "ALTER TABLE tenantapikey ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0;"
            )
            session.exec("ALTER TABLE tenantapikey ADD COLUMN created_at DATETIME;")
            session.exec("ALTER TABLE tenantapikey ADD COLUMN last_used DATETIME;")
            session.commit()
            logger.info("Migrated TenantApiKey table")
        except Exception:
            pass

    # migrating presets table
    with Session(engine) as session:
        try:
            logger.info("Migrating Preset table")
            session.exec(
                "ALTER TABLE preset ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT 0;"
            )
            session.exec(
                "ALTER TABLE preset ADD COLUMN created_by VARCHAR(1024) DEFAULT '';"
            )
            session.commit()
            logger.info("Migrated Preset table")
        except Exception:
            pass


def create_workflow_execution(
    workflow_id: str,
    tenant_id: str,
    triggered_by: str,
    execution_number: int = 1,
    fingerprint: str = None,
) -> WorkflowExecution:
    with Session(engine) as session:
        try:
            if len(triggered_by) > 255:
                triggered_by = triggered_by[:255]
            workflow_execution = WorkflowExecution(
                id=str(uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                started=datetime.now(tz=timezone.utc),
                triggered_by=triggered_by,
                execution_number=execution_number,
                status="in_progress",
            )
            session.add(workflow_execution)

            if fingerprint:
                workflow_to_alert_execution = WorkflowToAlertExecution(
                    workflow_execution_id=workflow_execution.id,
                    alert_fingerprint=fingerprint,
                )
                session.add(workflow_to_alert_execution)

            session.commit()
            return workflow_execution.id
        except IntegrityError:
            # Workflow execution already exists
            logger.debug(
                f"Failed to create a new execution for workflow {workflow_id}. Constraint is met."
            )
            raise


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
        workflows_with_interval = session.exec(
            select(Workflow)
            .where(Workflow.is_deleted == False)
            .where(Workflow.interval != None)
            .where(Workflow.interval > 0)
        ).all()

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
            select(WorkflowExecution)
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
    db_log_entries = [
        WorkflowExecutionLog(
            workflow_execution_id=log_entry["workflow_execution_id"],
            timestamp=datetime.strptime(log_entry["asctime"], "%Y-%m-%d %H:%M:%S,%f"),
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


def _enrich_alert(session, tenant_id, fingerprint, enrichments):
    enrichment = get_enrichment_with_session(session, tenant_id, fingerprint)
    if enrichment:
        # SQLAlchemy doesn't support updating JSON fields, so we need to do it manually
        # https://github.com/sqlalchemy/sqlalchemy/discussions/8396#discussion-4308891
        new_enrichment_data = {**enrichment.enrichments, **enrichments}
        stmt = (
            update(AlertEnrichment)
            .where(AlertEnrichment.id == enrichment.id)
            .values(enrichments=new_enrichment_data)
        )
        session.execute(stmt)
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
        session.commit()
        return alert_enrichment


def enrich_alert(tenant_id, fingerprint, enrichments, session=None):
    # else, the enrichment doesn't exist, create it
    if not session:
        with Session(engine) as session:
            return _enrich_alert(session, tenant_id, fingerprint, enrichments)
    return _enrich_alert(session, tenant_id, fingerprint, enrichments)


def get_enrichment(tenant_id, fingerprint):
    with Session(engine) as session:
        alert_enrichment = session.exec(
            select(AlertEnrichment)
            .where(AlertEnrichment.tenant_id == tenant_id)
            .where(AlertEnrichment.alert_fingerprint == fingerprint)
        ).first()
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


def get_enrichment_with_session(session, tenant_id, fingerprint):
    alert_enrichment = session.exec(
        select(AlertEnrichment)
        .where(AlertEnrichment.tenant_id == tenant_id)
        .where(AlertEnrichment.alert_fingerprint == fingerprint)
    ).first()
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
        query = query.join(Alert.alert_enrichment)

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


def get_last_alerts(tenant_id, provider_id=None, limit=1000) -> list[Alert]:
    """
    Get the last alert for each fingerprint.

    Args:
        tenant_id (_type_): The tenant_id to filter the alerts by.
        provider_id (_type_, optional): The provider id to filter by. Defaults to None.

    Returns:
        List[Alert]: A list of Alert objects.
    """
    with Session(engine) as session:
        # Start with a subquery that selects the max timestamp for each fingerprint.
        subquery = (
            session.query(
                Alert.fingerprint, func.max(Alert.timestamp).label("max_timestamp")
            )
            .filter(Alert.tenant_id == tenant_id)
            .group_by(Alert.fingerprint)
            .subquery()
        )

        query = (
            session.query(Alert)
            .join(
                subquery,
                and_(
                    Alert.fingerprint == subquery.c.fingerprint,
                    Alert.timestamp == subquery.c.max_timestamp,
                ),
            )
            .options(subqueryload(Alert.alert_enrichment))
        )

        # Filter by tenant_id
        query = query.filter(Alert.tenant_id == tenant_id)

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        # Order by timestamp in descending order and limit the results
        query = query.order_by(Alert.timestamp.desc()).limit(limit)
        # Execute the query
        alerts = query.all()

    return alerts


def get_alerts_by_fingerprint(tenant_id: str, fingerprint: str, limit=1) -> List[Alert]:
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

        if limit:
            query = query.limit(limit)
        # Execute the query
        alerts = query.all()

    return alerts


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
    grouping_criteria=[],
    group_description=None,
):
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
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule


def update_rule(
    tenant_id, rule_id, name, timeframe, definition, definition_cel, updated_by
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


def assign_alert_to_group(
    tenant_id, alert_id, rule_id, timeframe, group_fingerprint
) -> Group:
    # checks if group with the group critiria exists, if not it creates it
    #   and then assign the alert to the group
    with Session(engine) as session:
        group = session.exec(
            select(Group)
            .options(joinedload(Group.alerts))
            .where(Group.tenant_id == tenant_id)
            .where(Group.rule_id == rule_id)
            .where(Group.group_fingerprint == group_fingerprint)
            .order_by(Group.creation_time.desc())
        ).first()

        # if the last alert in the group is older than the timeframe, create a new group
        is_group_expired = False
        if group:
            # group has at least one alert (o/w it wouldn't created in the first place)
            is_group_expired = max(
                alert.timestamp for alert in group.alerts
            ) < datetime.utcnow() - timedelta(seconds=timeframe)

        if is_group_expired and group:
            logger.info(
                f"Group {group.id} is expired, creating a new group for rule {rule_id}"
            )
            fingerprint = group.calculate_fingerprint()
            # enrich the group with the expired flag
            enrich_alert(
                tenant_id,
                fingerprint,
                {"group_expired": True},
            )
            # change the group status to resolve so it won't spam the UI
            #   this was asked by @bhuvanesh and should be configurable in the future (how to handle status of expired groups)
            group_alert = session.exec(
                select(Alert)
                .where(Alert.fingerprint == fingerprint)
                .order_by(Alert.timestamp.desc())
            ).first()
            # this is kinda wtf but sometimes we deleted manually
            #   these from the DB since it was too big
            if not group_alert:
                logger.warning(
                    f"Group {group.id} is expired, but the alert is not found. Did it was deleted manually?"
                )
            else:
                group_alert.event["status"] = AlertStatus.RESOLVED.value
                # mark the event as modified so it will be updated in the database
                flag_modified(group_alert, "event")
            # commit the changes
            session.commit()
            logger.info(f"Enriched group {group.id} with group_expired flag")

        # if there is no group with the group_fingerprint, create it
        if not group or is_group_expired:
            # Create and add a new group if it doesn't exist
            group = Group(
                tenant_id=tenant_id,
                rule_id=rule_id,
                group_fingerprint=group_fingerprint,
            )
            session.add(group)
            session.commit()
            # Re-query the group with selectinload to set up future automatic loading of alerts
            group = session.exec(
                select(Group)
                .options(joinedload(Group.alerts))
                .where(Group.id == group.id)
            ).first()

        # Create a new AlertToGroup instance and add it
        alert_group = AlertToGroup(
            tenant_id=tenant_id,
            alert_id=str(alert_id),
            group_id=str(group.id),
        )
        session.add(alert_group)
        session.commit()
        # Requery the group to get the updated alerts
        group = session.exec(
            select(Group).options(joinedload(Group.alerts)).where(Group.id == group.id)
        ).first()
    return group


def get_groups(tenant_id):
    with Session(engine) as session:
        groups = session.exec(
            select(Group)
            .options(selectinload(Group.alerts))
            .where(Group.tenant_id == tenant_id)
        ).all()
    return groups


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
        if session.bind.dialect.name in ["mysql", "postgresql"]:
            time_format = "%Y-%m-%d %H:%i" if minute else "%Y-%m-%d %H"
            timestamp_format = func.date_format(AlertToGroup.timestamp, time_format)
        elif session.bind.dialect.name == "sqlite":
            time_format = "%Y-%m-%d %H:%M" if minute else "%Y-%m-%d %H"
            timestamp_format = func.strftime(time_format, AlertToGroup.timestamp)
        else:
            raise ValueError("Unsupported database dialect")
        # Construct the query
        query = (
            session.query(
                Rule.id.label("rule_id"),
                Rule.name.label("rule_name"),
                Group.id.label("group_id"),
                Group.group_fingerprint.label("group_fingerprint"),
                timestamp_format.label("time"),
                func.count(AlertToGroup.alert_id).label("hits"),
            )
            .join(Group, Rule.id == Group.rule_id)
            .join(AlertToGroup, Group.id == AlertToGroup.group_id)
            .filter(AlertToGroup.timestamp >= seven_days_ago)
            .filter(Rule.tenant_id == tenant_id)  # Filter by tenant_id
            .group_by(
                "rule_id", "rule_name", "group_id", "group_fingerprint", "time"
            )  # Adjusted here
            .order_by("time")
        )

        results = query.all()

        # Convert the results into a dictionary
        rule_distribution = {}
        for result in results:
            rule_id = result.rule_id
            group_fingerprint = result.group_fingerprint
            timestamp = result.time
            hits = result.hits

            if rule_id not in rule_distribution:
                rule_distribution[rule_id] = {}

            if group_fingerprint not in rule_distribution[rule_id]:
                rule_distribution[rule_id][group_fingerprint] = {}

            rule_distribution[rule_id][group_fingerprint][timestamp] = hits

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

        if session.bind.dialect.name in ["mysql", "postgresql"]:
            timestamp_format = func.date_format(Alert.timestamp, time_format)
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
