import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from uuid import uuid4

import pymysql
import validators
from dotenv import find_dotenv, load_dotenv
from google.cloud.sql.connector import Connector
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import String, and_, bindparam, case, desc, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload, subqueryload
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.db.alert import *
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
            # Do everything related with single tenant creation in here
            session.add(Tenant(id=tenant_id, name="Single Tenant"))
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
            session.commit()
        except IntegrityError:
            # Tenant already exists
            pass
        except Exception:
            pass


def create_workflow_execution(
    workflow_id: str, tenant_id: str, triggered_by: str, execution_number: int = 1
) -> WorkflowExecution:
    with Session(engine) as session:
        try:
            workflow_execution = WorkflowExecution(
                id=str(uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                started=datetime.utcnow(),
                triggered_by=triggered_by,
                execution_number=execution_number,
                status="in_progress",
            )
            session.add(workflow_execution)
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


def get_workflows_with_last_execution(tenant_id: str) -> List[dict]:
    with Session(engine) as session:
        latest_execution_cte = (
            select(
                WorkflowExecution.workflow_id,
                func.max(WorkflowExecution.started).label("last_execution_time"),
            )
            .group_by(WorkflowExecution.workflow_id)
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
        )

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
        workflow_execution.error = error
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


def enrich_alert(tenant_id, fingerprint, enrichments):
    # else, the enrichment doesn't exist, create it
    with Session(engine) as session:
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


def get_alerts_with_filters(tenant_id, provider_id=None, filters=None):
    with Session(engine) as session:
        # Create the query
        query = session.query(Alert)

        # Apply subqueryload to force-load the alert_enrichment relationship
        query = query.options(subqueryload(Alert.alert_enrichment))

        # Filter by tenant_id
        query = query.filter(Alert.tenant_id == tenant_id)

        # Ensure Alert and AlertEnrichment are joined for subsequent filters
        query = query.join(Alert.alert_enrichment)

        # Apply filters if provided
        if filters:
            for f in filters:
                filter_key, filter_value = f.get("key"), f.get("value")
                query = query.filter(
                    AlertEnrichment.enrichments[filter_key] == filter_value
                )

        if provider_id:
            query = query.filter(Alert.provider_id == provider_id)

        # Execute the query
        alerts = query.all()

    return alerts


def get_last_alerts(tenant_id, provider_id=None) -> list[Alert]:
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

        # Execute the query
        alerts = query.all()

    return alerts


def get_alerts_by_fingerprint(tenant_id: str, fingerprint: str) -> List[Alert]:
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

        # Execute the query
        alerts = query.all()

    return alerts


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


def create_rule(tenant_id, name, timeframe, definition, definition_cel, created_by):
    with Session(engine) as session:
        rule = Rule(
            tenant_id=tenant_id,
            name=name,
            timeframe=timeframe,
            definition=definition,
            definition_cel=definition_cel,
            created_by=created_by,
            creation_time=datetime.utcnow(),
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


def get_rules(tenant_id):
    with Session(engine) as session:
        rules = session.exec(select(Rule).where(Rule.tenant_id == tenant_id)).all()
    return rules


def run_rule(tenant_id, rule):
    """This function implements the rule engine logic.

    We currently support two sql engines: mysql and sqlite.

    The complexity of this function derives from the fact that we need to support nested JSON attributes.


    Args:
        tenant_id (str): the tenant_id
        rule (Rule): the rule

    """
    with Session(engine) as session:
        # get all the alerts that are not already in the rule
        sql = rule.definition.get("sql")
        params = rule.definition.get("params")

        timeframe_datetime = datetime.utcnow() - timedelta(seconds=rule.timeframe)

        groups = re.split(r"\s+and\s+(?![^()]*\))", sql)

        results_per_group = {}
        for group in groups:
            # Removing outer parentheses and spaces
            group = group.strip().strip("()").strip()

            # Building the text object for the filter part
            filter_text = text(group)
            # find the params it needs
            bind_names = [str(p) for p in filter_text._bindparams]

            # Applying bindparams with expanding for lists
            filters = []
            for bind in bind_names:
                value = params.get(bind)
                # TODO: we use 'like' and 'json_contains' but
                #       we need to support other operators like =, !=, >, <, etc
                #       down the road we will need to adjust this to support other types (dict?)
                #       the problem is that we need to know upfront what's the type of the attribute in nested JSON
                #       which is not trivial

                # source_1 => source, severity_2 => severity
                attribute_name = bind.split("_")[0]
                json_path = f"$.{attribute_name}"
                # Handling different SQL dialects
                if session.bind.dialect.name == "mysql":
                    json_extracted = func.json_extract(Alert.event, json_path)
                    json_type = func.json_type(json_extracted)

                    condition = case(
                        [
                            (
                                json_type == "ARRAY",
                                func.json_contains(
                                    json_extracted,
                                    func.json_array(bindparam(bind, value)),
                                )
                                == 1,
                            ),
                            (
                                json_type == "STRING",
                                json_extracted.like("%" + bindparam(bind, value) + "%"),
                            ),
                            (
                                json_type == "OBJECT",
                                func.cast(json_extracted, String).like(value),
                            ),
                        ],
                        else_=False,
                    )
                    filters.append(condition)
                # else, sqlite
                elif session.bind.dialect.name == "sqlite":
                    json_extracted = func.json_extract(Alert.event, json_path)
                    # Determine the type of the JSON field
                    json_type = func.json_type(Alert.event, json_path)

                    # This example assumes that the value you are looking for is a simple scalar value (like a string or a number).
                    # Adjust the logic if you need to support complex nested objects.
                    condition = case(
                        [
                            # If the field is an array, use LIKE operator for matching
                            (
                                json_type == "array",
                                json_extracted.like(
                                    '%"' + bindparam(bind, value) + '"%'
                                ),
                            ),
                            # If the field is an object, use string matching. This is a workaround and has limitations.
                            (
                                json_type == "object",
                                json_extracted.like(
                                    '%"' + bindparam(bind, value) + '"%'
                                ),
                            ),
                        ],
                        else_=json_extracted.like(
                            bindparam(bind, value)
                        ),  # Default case for other types like string
                    )
                    filters.append(condition)
                else:
                    raise Exception(
                        f"Unsupported SQL dialect for Rules Engine: {session.bind.dialect.name}"
                    )

            # add the tenant_id and timeframe filters
            filters.append(Alert.tenant_id == tenant_id)
            # TODO: maybe timeframe should support lastReceived? but idk if there is a use case for that
            filters.append(Alert.timestamp >= timeframe_datetime)
            # Exclude events created by the rule engine itself
            filters.append(Alert.provider_type != "rules")
            # Construct and execute the ORM query
            query = session.query(Alert).filter(*filters)
            # Shahar: to get the RAW query -
            #         from sqlalchemy.sql import compiler
            #         from sqlalchemy.dialects import mysql, sqlite
            #         str(query.params(params).statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
            result = query.all()
            results_per_group[group] = result

        # if each group have at least one alert, than the run applies
        if all(results_per_group.values()):
            return results_per_group

        # otherwise, it doesn't
        return None


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


def assign_alert_to_group(tenant_id, alert_id, rule_id, group_fingerprint):
    # checks if group with the group critiria exists, if not it creates it
    #   and then assign the alert to the group
    with Session(engine) as session:
        group = session.exec(
            select(Group)
            .where(Group.tenant_id == tenant_id)
            .where(Group.rule_id == rule_id)
            .where(Group.group_fingerprint == group_fingerprint)
        ).first()
        # if the group does not exist
        if not group:
            group = Group(
                tenant_id=tenant_id,
                rule_id=rule_id,
                group_fingerprint=group_fingerprint,
            )
            session.add(group)
            session.commit()
            session.refresh(group)

        alert_group = AlertToGroup(
            tenant_id=tenant_id,
            alert_id=str(alert_id),
            group_id=str(group.id),
        )
        session.add(alert_group)
        session.commit()
        session.refresh(alert_group)
        return alert_group


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
