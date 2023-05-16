import hashlib
import os

import pymysql
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from google.cloud.sql.connector import Connector
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.core.config import config
from keep.api.models.db.tenant import *

running_in_cloud_run = os.environ.get("K_SERVICE") is not None


def get_conn() -> pymysql.connections.Connection:
    with Connector() as connector:
        conn = connector.connect(
            "keephq-sandbox:us-central1:keep",  # Todo: get from configuration
            "pymysql",
            user="keep-auth",
            db="keepdb",
            enable_iam_auth=True,
        )
    return conn


def get_conn_impersonate() -> pymysql.connections.Connection:
    from google.auth import default, impersonated_credentials
    from google.auth.transport.requests import Request

    # Get application default credentials
    creds, project = default()
    # Create impersonated credentials
    target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal="keep-auth@keephq-sandbox.iam.gserviceaccount.com",
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
            user="keep-auth",
            password=access_token,
            host="127.0.0.1",
            port=3306,
            database="keepdb",
        )
    return conn


connect_args = {"check_same_thread": False}

if running_in_cloud_run:
    engine = create_engine(
        "mysql+pymysql://", creator=get_conn, connect_args=connect_args
    )
elif config("DATABASE_CONNECTION_STRING", default=None):
    engine = create_engine(
        config("DATABASE_CONNECTION_STRING"), connect_args=connect_args
    )
else:
    engine = create_engine(
        "mysql+pymysql://", creator=get_conn_impersonate, connect_args=connect_args
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


auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key")


def verify_customer(
    api_key: str = Security(auth_header), session: Session = Depends(get_session)
) -> TenantApiKey:
    """
    Verifies that a customer is allowed to access the API.

    Args:
        api_key (str, optional): The API key extracted from X-API-KEY header. Defaults to Security(auth_header).
        session (Session, optional): A databse session. Defaults to Depends(get_session).

    Raises:
        HTTPException: 401 if the user is unauthorized.

    Returns:
        TenantApiKey: The tenant API key resource including the Tenant resource.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")

    api_key_hashed = hashlib.sha256(api_key.encode()).hexdigest()

    statement = select(TenantApiKey).where(TenantApiKey.key_hash == api_key_hashed)
    tenant_api_key = session.exec(statement).first()
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return tenant_api_key
