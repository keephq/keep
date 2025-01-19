"""
This module contains the database utilities.

Mainly, it creates the database engine based on the environment variables.
"""

import json
import logging
import os

import pymysql
from dotenv import find_dotenv, load_dotenv
from google.cloud.sql.connector import Connector
from sqlalchemy import func
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.ddl import CreateColumn
from sqlalchemy.sql.functions import GenericFunction
from sqlmodel import Session, create_engine

# This import is required to create the tables
from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config

logger = logging.getLogger(__name__)


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
    from google.auth import (  # pylint: disable=import-outside-toplevel
        default,
        impersonated_credentials,
    )
    from google.auth.transport.requests import (  # pylint: disable=import-outside-toplevel
        Request,
    )

    # Get application default credentials
    creds, _ = default()
    # Create impersonated credentials
    target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    service_account = os.environ.get("DB_SERVICE_ACCOUNT")
    creds = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal=service_account,
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

DB_CONNECTION_STRING = config(
    "DATABASE_CONNECTION_STRING", default=None
)  # pylint: disable=invalid-name
DB_POOL_SIZE = config(
    "DATABASE_POOL_SIZE", default=5, cast=int
)  # pylint: disable=invalid-name
DB_MAX_OVERFLOW = config(
    "DATABASE_MAX_OVERFLOW", default=10, cast=int
)  # pylint: disable=invalid-name
DB_ECHO = config(
    "DATABASE_ECHO", default=False, cast=bool
)  # pylint: disable=invalid-name
KEEP_FORCE_CONNECTION_STRING = config(
    "KEEP_FORCE_CONNECTION_STRING", default=False, cast=bool
)  # pylint: disable=invalid-name
KEEP_DB_PRE_PING_ENABLED = config(
    "KEEP_DB_PRE_PING_ENABLED", default=False, cast=bool
)  # pylint: disable=invalid-name


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


def create_db_engine():
    """
    Creates a database engine based on the environment variables.
    """
    if RUNNING_IN_CLOUD_RUN and not KEEP_FORCE_CONNECTION_STRING:
        engine = create_engine(
            "mysql+pymysql://",
            creator=__get_conn,
            echo=DB_ECHO,
            json_serializer=dumps,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
        )
    elif DB_CONNECTION_STRING == "impersonate":
        engine = create_engine(
            "mysql+pymysql://",
            creator=__get_conn_impersonate,
            echo=DB_ECHO,
            json_serializer=dumps,
        )
    elif DB_CONNECTION_STRING:
        try:
            logger.info(f"Creating a connection pool with size {DB_POOL_SIZE}")
            engine = create_engine(
                DB_CONNECTION_STRING,
                pool_size=DB_POOL_SIZE,
                max_overflow=DB_MAX_OVERFLOW,
                json_serializer=dumps,
                echo=DB_ECHO,
                pool_pre_ping=True if KEEP_DB_PRE_PING_ENABLED else False,
            )
        # SQLite does not support pool_size
        except TypeError:
            engine = create_engine(
                DB_CONNECTION_STRING, json_serializer=dumps, echo=DB_ECHO
            )
    else:
        engine = create_engine(
            "sqlite:///./keep.db",
            connect_args={"check_same_thread": False},
            echo=DB_ECHO,
            json_serializer=dumps,
        )
    return engine


def create_async_db_engine():
    """
    Creates an async database engine based on the environment variables.
    """
    if RUNNING_IN_CLOUD_RUN and not KEEP_FORCE_CONNECTION_STRING:
        # For MySQL in Cloud Run
        engine = create_async_engine(
            "mysql+aiomysql://",
            creator=__get_conn,  # Note: You'll need an async version of this
            echo=DB_ECHO,
            json_serializer=dumps,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
        )
    elif DB_CONNECTION_STRING == "impersonate":
        # For MySQL with impersonation
        engine = create_async_engine(
            "mysql+aiomysql://",
            creator=__get_conn_impersonate,  # Note: You'll need an async version of this
            echo=DB_ECHO,
            json_serializer=dumps,
        )
    elif DB_CONNECTION_STRING:
        try:
            logger.info(f"Creating an async connection pool with size {DB_POOL_SIZE}")
            # Convert connection string to async version
            async_connection_string = DB_CONNECTION_STRING
            if DB_CONNECTION_STRING.startswith("mysql"):
                async_connection_string = DB_CONNECTION_STRING.replace(
                    "mysql:", "mysql+aiomysql:"
                )
            # support psycopg2
            elif DB_CONNECTION_STRING.startswith("postgresql+psycopg2"):
                async_connection_string = DB_CONNECTION_STRING.replace(
                    "postgresql+psycopg2:", "postgresql+asyncpg:"
                )
            # support postgres without psycopg2
            elif DB_CONNECTION_STRING.startswith("postgresql"):
                async_connection_string = DB_CONNECTION_STRING.replace(
                    "postgresql:", "postgresql+asyncpg:"
                )
            elif "sqlite://" in DB_CONNECTION_STRING:
                async_connection_string = DB_CONNECTION_STRING.replace(
                    "sqlite://", "sqlite+aiosqlite://"
                )

            engine = create_async_engine(
                async_connection_string,
                pool_size=(
                    DB_POOL_SIZE if "sqlite" not in async_connection_string else None
                ),
                max_overflow=(
                    DB_MAX_OVERFLOW if "sqlite" not in async_connection_string else None
                ),
                json_serializer=dumps,
                echo=DB_ECHO,
                pool_pre_ping=True if KEEP_DB_PRE_PING_ENABLED else False,
            )
        # SQLite does not support pool_size
        except TypeError:
            # For SQLite, use aiosqlite
            async_connection_string = DB_CONNECTION_STRING.replace(
                "sqlite:", "sqlite+aiosqlite:"
            )
            engine = create_async_engine(
                async_connection_string,
                json_serializer=dumps,
                echo=DB_ECHO,
            )
    else:
        # Default SQLite case
        engine = create_async_engine(
            "sqlite+aiosqlite:///./keep.db",
            connect_args={"check_same_thread": False},
            echo=DB_ECHO,
            json_serializer=dumps,
        )
    return engine


def get_json_extract_field(session, base_field, key):
    if session.bind.dialect.name == "postgresql":
        return func.json_extract_path_text(base_field, key)
    elif session.bind.dialect.name == "mysql":
        return func.json_unquote(func.json_extract(base_field, "$.{}".format(key)))
    else:
        return func.json_extract(base_field, "$.{}".format(key))


def get_aggreated_field(session: Session, column_name: str, alias: str):
    if session.bind is None:
        raise ValueError("Session is not bound to a database")

    if session.bind.dialect.name == "postgresql":
        return func.array_agg(column_name).label(alias)
    elif session.bind.dialect.name == "mysql":
        return func.json_arrayagg(column_name).label(alias)
    elif session.bind.dialect.name == "sqlite":
        return func.group_concat(column_name).label(alias)
    else:
        return func.array_agg(column_name).label(alias)


class json_table(GenericFunction):
    inherit_cache = True


@compiles(json_table, "mysql")
def _compile_json_table(element, compiler, **kw):
    ddl_compiler = compiler.dialect.ddl_compiler(compiler.dialect, None)
    return "JSON_TABLE({}, '$[*]' COLUMNS({} PATH '$'))".format(
        compiler.process(element.clauses.clauses[0], **kw),
        ",".join(
            ddl_compiler.process(CreateColumn(clause), **kw)
            for clause in element.clauses.clauses[1:]
        ),
    )
