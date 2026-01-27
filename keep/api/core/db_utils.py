"""
This module contains the database utilities.

Mainly, it creates the database engine based on the environment variables.
"""

import json
import logging
import os
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Type, TypeVar

import pymysql
from dotenv import find_dotenv, load_dotenv
from fastapi.encoders import jsonable_encoder
from google.cloud.sql.connector import Connector
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.ddl import CreateColumn
from sqlalchemy.sql.functions import GenericFunction
from sqlmodel import Session, SQLModel, create_engine, select

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
            ip_type=os.environ.get("DB_IP_TYPE", "public"),
            user=os.environ.get("DB_SERVICE_ACCOUNT", "keep-api"),
            db=os.environ.get("DB_NAME", "keepdb"),
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
            database=os.environ.get("DB_NAME", "keepdb"),
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
DB_POOL_RECYCLE = config(
    "DATABASE_POOL_RECYCLE", default=3600, cast=int
)  # pylint: disable=invalid-name
DB_POOL_TIMEOUT = config(
    "DATABASE_POOL_TIMEOUT", default=30, cast=int
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
            pool_recycle=DB_POOL_RECYCLE,
            pool_timeout=DB_POOL_TIMEOUT,
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
                pool_recycle=DB_POOL_RECYCLE,
                pool_timeout=DB_POOL_TIMEOUT,
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


T = TypeVar("T", bound=SQLModel)


def get_or_create(
    session: Session,
    model: Type[T],
    defaults: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Tuple[T, bool]:
    """
    Get an instance by filter kwargs, or create one with those filters plus any defaults.

    Args:
        session: SQLModel session
        model: Model class
        defaults: Dict of default values for creation (not used for lookup)
        **kwargs: Filter parameters used both for lookup and creation

    Returns:
        tuple: (instance, created) where created is a boolean indicating if a new instance was created
    """
    # Build query with all filter conditions
    query = select(model)
    for key, value in kwargs.items():
        query = query.where(getattr(model, key) == value)

    # Execute the query
    instance = session.exec(query).first()

    if instance:
        return instance, False

    # Prepare creation attributes
    create_attrs = kwargs.copy()
    if defaults:
        create_attrs.update(defaults)

    instance = model(**create_attrs)
    session.add(instance)

    try:
        # Try to flush without committing to detect any integrity errors
        session.flush()
        return instance, True
    except IntegrityError:
        # If there's a conflict, roll back and try to fetch again (another process might have created it)
        session.rollback()

        # Try to fetch again with the same query
        instance = session.exec(query).first()
        if instance:
            return instance, False
        # If we still can't find it, something else is wrong, re-raise
        raise


def custom_serialize(obj: Any) -> Any:
    """
    Custom serializer that handles Pydantic models (like AlertDto) and other complex types.
    """
    if isinstance(obj, dict):
        return {k: custom_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [custom_serialize(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(custom_serialize(item) for item in obj)
    elif isinstance(obj, BaseModel):
        # For Pydantic models like AlertDto
        return obj.dict()
    elif isinstance(obj, Enum):
        # For enum values
        return obj.value
    else:
        # For other objects, try jsonable_encoder, which handles many edge cases
        try:
            return jsonable_encoder(obj)
        except Exception:
            # If even jsonable_encoder fails, convert to string as a last resort
            return str(obj)
