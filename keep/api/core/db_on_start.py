import hashlib
import json
import logging
import os

import pymysql
from dotenv import find_dotenv, load_dotenv
from google.cloud.sql.connector import Connector
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import create_database, database_exists
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config
from keep.api.core.rbac import Admin as AdminRole
from keep.api.models.db.alert import *
from keep.api.models.db.dashboard import *
from keep.api.models.db.extraction import *
from keep.api.models.db.mapping import *
from keep.api.models.db.preset import *
from keep.api.models.db.provider import *
from keep.api.models.db.rule import *
from keep.api.models.db.tenant import *
from keep.api.models.db.workflow import *

logger = logging.getLogger(__name__)


def on_connect(dbapi_connection, connection_record):
    logger.info("Establishing")
    cursor = dbapi_connection.cursor()
    logger.info("Established")
    cursor.execute("SELECT pg_backend_pid()")
    logger.info("Executed")
    connection_id = cursor.fetchone()[0]
    logger.info(f"Fetched - connection id {connection_id}")
    # setattr(dbapi_connection, 'keep_connection_id', connection_id)
    logger.info(f"New database connection established: {connection_id}")
    cursor.close()


def __get_conn() -> pymysql.connections.Connection:
    """
    Creates a connection to the database when running in Cloud Run.

    Returns:
        pymysql.connections.Connection: The DB connection.
    """
    with Connector() as connector:
        conn = connector.connect(
            os.environ.get("DB_CONNECTION_NAME", "keephq-sandbox:us-central1:keep"),
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
            os.environ.get("DB_CONNECTION_NAME", "keephq-sandbox:us-central1:keep"),
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
max_overflow = config("DATABASE_MAX_OVERFLOW", default=10, cast=int)


def dumps(_json) -> str:
    """
    Overcome the issue of serializing datetime objects to JSON with the default json.dumps.
       Usually seen with PostgreSQL JSONB fields.
    https://stackoverflow.com/questions/36438052/using-a-custom-json-encoder-for-sqlalchemys-postgresql-jsonb-implementation

    Args:
        _json (object): The json object to serialize.

    Returns:
        str: The serialized JSON object.
    """
    return json.dumps(_json, default=str)


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
        engine = create_engine(
            db_connection_string,
            pool_size=pool_size,
            max_overflow=max_overflow,
            json_serializer=dumps,
            echo=True,
        )
    # SQLite does not support pool_size
    except TypeError:
        engine = create_engine(db_connection_string)
else:
    engine = create_engine(
        "sqlite:///./keep.db", connect_args={"check_same_thread": False}
    )


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
            logger.info("Single tenant created")
        except IntegrityError:
            # Tenant already exists
            logger.info("Single tenant already exists")
            pass
        except Exception:
            logger.exception("Failed to create single tenant")
            pass


def create_db_and_tables():
    """
    Creates the database and tables.
    """
    try:
        new_engine = create_engine(
            db_connection_string,
            pool_size=pool_size,
            max_overflow=max_overflow,
            json_serializer=dumps,
        )
        if not database_exists(new_engine.url):
            logger.info("Creating the database")
            create_database(new_engine.url)
            logger.info("Database created")
    # On Cloud Run, it fails to check if the database exists
    except Exception:
        logger.warning("Failed to create the database or detect if it exists.")
        pass

    logger.info("Creating the tables")
    SQLModel.metadata.create_all(new_engine)
    logger.info("Tables created")
