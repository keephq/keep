import logging
import os
import time
from datetime import datetime, timedelta
from uuid import uuid4

import pymysql
from google.cloud.sql.connector import Connector
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, joinedload
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.core.config import config
from keep.api.models.db.alert import *
from keep.api.models.db.provider import *
from keep.api.models.db.tenant import *
from keep.api.models.db.workflow import *

running_in_cloud_run = os.environ.get("K_SERVICE") is not None

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


db_connection_string = config("DATABASE_CONNECTION_STRING", default=None)

if running_in_cloud_run:
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
    engine = create_engine(
        db_connection_string,
    )
else:
    engine = create_engine(
        "sqlite:///./keep.db", connect_args={"check_same_thread": False}
    )


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
    with Session(engine) as session:
        yield session


def try_create_single_tenant(tenant_id: str) -> None:
    try:
        create_db_and_tables()
    except:
        pass
    with Session(engine) as session:
        try:
            # Do everything related with single tenant creation in here
            session.add(Tenant(id=tenant_id, name="Single Tenant"))
            session.commit()
        except IntegrityError:
            # Tenant already exists
            pass


def create_workflow_execution(
    workflow_id: str, tenant_id: str, triggered_by: str
) -> WorkflowExecution:
    with Session(engine) as session:
        workflow_execution = WorkflowExecution(
            id=str(uuid4()),
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            started=datetime.utcnow(),
            triggered_by=triggered_by,
            status="in_progress",
        )
        session.add(workflow_execution)
        session.commit()
        return workflow_execution.id


def get_last_completed_execution(
    session: Session, workflow_id: str
) -> WorkflowExecution:
    return session.exec(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .where(
            (WorkflowExecution.status == "success")
            | (WorkflowExecution.status == "error")
        )
        .order_by(WorkflowExecution.started.desc())
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

        for workflow in workflows_with_interval:
            current_time = datetime.utcnow()
            last_execution = get_last_completed_execution(session, workflow.id)

            if not last_execution or (
                last_execution.started + timedelta(seconds=workflow.interval)
                <= current_time
            ):
                ongoing_execution = session.exec(
                    select(WorkflowExecution)
                    .where(WorkflowExecution.workflow_id == workflow.id)
                    .where(WorkflowExecution.status == "in_progress")
                ).first()

                if not ongoing_execution:
                    workflow_execution_id = create_workflow_execution(
                        workflow.id, workflow.tenant_id, "scheduler"
                    )
                    # the workflow obejct itself is only under this session so we need to use the
                    # raw
                    workflows_to_run.append(
                        {
                            "tenant_id": workflow.tenant_id,
                            "workflow_id": workflow.id,
                            "workflow_execution_id": workflow_execution_id,
                        }
                    )
                # if there is ongoing execution, check if it is running for more than 60 minutes and if so
                # mark it as timeout
                elif ongoing_execution.started + timedelta(minutes=60) <= current_time:
                    ongoing_execution.status = "timeout"
                    session.commit()
                    # re-create the execution
                    workflow_execution_id = create_workflow_execution(
                        workflow.id, workflow.tenant_id, "scheduler"
                    )
                    # the workflow obejct itself is only under this session so we need to use the
                    # raw
                    workflows_to_run.append(
                        {
                            "tenant_id": workflow.tenant_id,
                            "workflow_id": workflow.id,
                            "workflow_execution_id": workflow_execution_id,
                        }
                    )
                else:
                    logger.info(f"Workflow {workflow.id} is already running")

        return workflows_to_run


def add_workflow(
    id, name, tenant_id, description, created_by, interval, workflow_raw
) -> Workflow:
    with Session(engine) as session:
        workflow = Workflow(
            id=id,
            name=name,
            tenant_id=tenant_id,
            description=description,
            created_by=created_by,
            interval=interval,
            workflow_raw=workflow_raw,
        )
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
    return workflow


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


def get_workflow(tenant_id: str, workflow_id: str) -> str:
    with Session(engine) as session:
        workflow = session.exec(
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .where(Workflow.id == workflow_id)
            .where(Workflow.is_deleted == False)
        ).first()
    if not workflow:
        return None
    return workflow.workflow_raw


def get_installed_providers(tenant_id: str) -> List[str]:
    with Session(engine) as session:
        providers = session.exec(
            select(Provider).where(Provider.tenant_id == tenant_id)
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
            time.time() - workflow_execution.started.timestamp()
        )
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
        ).first()

        if workflow:
            return workflow.id


def push_logs_to_db(log_entries):
    db_log_entries = [
        WorkflowExecutionLog(
            workflow_execution_id=log_entry["workflow_execution_id"],
            timestamp=datetime.strptime(log_entry["asctime"], "%Y-%m-%d %H:%M:%S,%f"),
            message=log_entry["message"],
        )
        for log_entry in log_entries
    ]

    # Add the LogEntry instances to the database session
    with Session(engine) as session:
        session.add_all(db_log_entries)
        session.commit()


def get_workflow_execution(
    tenant_id: str, workflow_id: str, workflow_execution_id: str
):
    with Session(engine) as session:
        execution_with_logs = (
            session.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.id == workflow_execution_id,
            )
            .options(joinedload(WorkflowExecution.logs))
            .one()
        )

        return execution_with_logs
    return execution_with_logs
