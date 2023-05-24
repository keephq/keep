import os

import pymysql
from google.cloud.sql.connector import Connector
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

# This import is required to create the tables
from keep.api.core.config import config
from keep.api.models.db.tenant import *

running_in_cloud_run = os.environ.get("K_SERVICE") is not None


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


connect_args = {"check_same_thread": False}

if running_in_cloud_run:
    engine = create_engine(
        "mysql+pymysql://", creator=__get_conn, connect_args=connect_args
    )
elif config("DATABASE_CONNECTION_STRING", default=None):
    engine = create_engine(
        config("DATABASE_CONNECTION_STRING"), connect_args=connect_args
    )
else:
    engine = create_engine(
        "mysql+pymysql://", creator=__get_conn_impersonate, connect_args=connect_args
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


def create_single_tenant(tenant_id: str) -> None:
    with Session(engine) as session:
        try:
            # Do everything related with single tenant creation in here
            session.add(Tenant(id=tenant_id, name="Single Tenant"))
            session.commit()
        except IntegrityError:
            # Tenant already exists
            pass
