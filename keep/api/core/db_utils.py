"""
Database utilities.

Responsibilities:
- Create the SQLAlchemy/SQLModel engine based on environment/config
- Provide a small set of dialect-aware helpers (JSON extract, aggregation)
- Provide safe-ish get_or_create helper
- Provide serialization helper for complex types

Important:
- This module should NOT mutate process environment (no load_dotenv at import time).
- Cloud SQL Connector should be long-lived; do not create/close Connector per connection.
"""

from __future__ import annotations

import json
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Type, TypeVar

import pymysql
from fastapi.encoders import jsonable_encoder
from google.cloud.sql.connector import Connector
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.ddl import CreateColumn
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, SQLModel, create_engine, select

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)

# ---------------------------
# Config
# ---------------------------

DB_CONNECTION_STRING: Optional[str] = config("DATABASE_CONNECTION_STRING", default=None)
DB_POOL_SIZE: int = config("DATABASE_POOL_SIZE", default=5, cast=int)
DB_MAX_OVERFLOW: int = config("DATABASE_MAX_OVERFLOW", default=10, cast=int)
DB_ECHO: bool = config("DATABASE_ECHO", default=False, cast=bool)
KEEP_FORCE_CONNECTION_STRING: bool = config(
    "KEEP_FORCE_CONNECTION_STRING", default=False, cast=bool
)
KEEP_DB_PRE_PING_ENABLED: bool = config(
    "KEEP_DB_PRE_PING_ENABLED", default=False, cast=bool
)

# Optional: let ops control pool recycle for MySQL.
DB_POOL_RECYCLE_SECONDS: int = config("DATABASE_POOL_RECYCLE", default=1800, cast=int)


# ---------------------------
# JSON serializer helper
# ---------------------------

def dumps(_json: Any) -> str:
    """
    JSON serializer that won't choke on datetime/UUID/etc.
    """
    return json.dumps(_json, default=str)


# ---------------------------
# Cloud SQL Connector (long-lived singleton)
# ---------------------------

_connector: Optional[Connector] = None


def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector


def _cloudsql_connect_iam() -> pymysql.connections.Connection:
    """
    Cloud Run / IAM auth connection creator for Cloud SQL MySQL.
    Intended for SQLAlchemy engine `creator=...`.
    """
    connector = _get_connector()
    return connector.connect(
        os.environ.get("DB_CONNECTION_NAME", "keephq-sandbox:us-central1:keep"),
        "pymysql",
        ip_type=os.environ.get("DB_IP_TYPE", "public"),
        user=os.environ.get("DB_SERVICE_ACCOUNT", "keep-api"),
        db=os.environ.get("DB_NAME", "keepdb"),
        enable_iam_auth=True,
    )


def _cloudsql_connect_impersonate_local() -> pymysql.connections.Connection:
    """
    Local impersonation connection creator.

    NOTE:
    This assumes you have a local proxy/tunnel available if required.
    If not, this will fail. Document the setup in deployment docs.
    """
    from google.auth import default, impersonated_credentials  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore

    creds, _ = default()
    service_account = os.environ.get("DB_SERVICE_ACCOUNT")
    if not service_account:
        raise RuntimeError("DB_SERVICE_ACCOUNT must be set for impersonation mode")

    target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    imp_creds = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal=service_account,
        target_scopes=target_scopes,
    )
    imp_creds.refresh(Request())
    access_token = imp_creds.token
    if not access_token:
        raise RuntimeError("Failed to obtain impersonated access token")

    connector = _get_connector()
    return connector.connect(
        os.environ.get("DB_CONNECTION_NAME", "keephq-sandbox:us-central1:keep"),
        "pymysql",
        user=os.environ.get("DB_LOCAL_USER", "keep-api"),
        password=access_token,
        host=os.environ.get("DB_LOCAL_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_LOCAL_PORT", "3306")),
        db=os.environ.get("DB_NAME", "keepdb"),
    )


# ---------------------------
# Engine creation
# ---------------------------

_engine: Optional[Engine] = None


def create_db_engine(*, force_new: bool = False) -> Engine:
    """
    Create (or return cached) SQLAlchemy Engine.

    Each process should create its own engine (fork safety).
    If you want to ensure no caching (tests), pass force_new=True.
    """
    global _engine
    if _engine is not None and not force_new:
        return _engine

    engine: Engine

    # Common pool args for MySQL/connection-string cases
    common_engine_kwargs: Dict[str, Any] = {
        "echo": DB_ECHO,
        "json_serializer": dumps,
    }

    if RUNNING_IN_CLOUD_RUN and not KEEP_FORCE_CONNECTION_STRING:
        # Cloud Run + Cloud SQL Connector IAM
        engine = create_engine(
            "mysql+pymysql://",
            creator=_cloudsql_connect_iam,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_pre_ping=KEEP_DB_PRE_PING_ENABLED,
            pool_recycle=DB_POOL_RECYCLE_SECONDS,
            **common_engine_kwargs,
        )
    elif DB_CONNECTION_STRING == "impersonate":
        engine = create_engine(
            "mysql+pymysql://",
            creator=_cloudsql_connect_impersonate_local,
            pool_pre_ping=KEEP_DB_PRE_PING_ENABLED,
            pool_recycle=DB_POOL_RECYCLE_SECONDS,
            **common_engine_kwargs,
        )
    elif DB_CONNECTION_STRING:
        try:
            logger.info("Creating DB engine. pool_size=%s max_overflow=%s pre_ping=%s",
                        DB_POOL_SIZE, DB_MAX_OVERFLOW, KEEP_DB_PRE_PING_ENABLED)
            engine = create_engine(
                DB_CONNECTION_STRING,
                pool_size=DB_POOL_SIZE,
                max_overflow=DB_MAX_OVERFLOW,
                pool_pre_ping=KEEP_DB_PRE_PING_ENABLED,
                pool_recycle=DB_POOL_RECYCLE_SECONDS,
                **common_engine_kwargs,
            )
        except TypeError:
            # SQLite and some dialects don't accept pool args
            engine = create_engine(DB_CONNECTION_STRING, **common_engine_kwargs)
    else:
        # Local sqlite fallback
        engine = create_engine(
            "sqlite:///./keep.db",
            connect_args={"check_same_thread": False},
            **common_engine_kwargs,
        )

    _engine = engine
    return engine


# ---------------------------
# Dialect helpers
# ---------------------------

_JSON_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def get_json_extract_field(session: Session, base_field: ColumnElement[Any], key: str):
    """
    Dialect-aware JSON field extraction.

    Security: key must be a simple identifier (letters/digits/_).
    """
    if not _JSON_KEY_RE.match(key):
        raise ValueError(f"Invalid JSON key: {key!r}")

    bind = session.get_bind()
    if bind is None:
        raise ValueError("Session is not bound to a database")

    dialect = bind.dialect.name
    if dialect == "postgresql":
        return func.json_extract_path_text(base_field, key)
    if dialect == "mysql":
        return func.json_unquote(func.json_extract(base_field, f"$.{key}"))
    # sqlite
    return func.json_extract(base_field, f"$.{key}")


def get_aggregated_field(session: Session, column: ColumnElement[Any], alias: str):
    """
    Dialect-aware aggregation wrapper.

    column must be a SQL expression/column, NOT a string.
    """
    bind = session.get_bind()
    if bind is None:
        raise ValueError("Session is not bound to a database")

    dialect = bind.dialect.name
    if dialect == "postgresql":
        return func.array_agg(column).label(alias)
    if dialect == "mysql":
        return func.json_arrayagg(column).label(alias)
    if dialect == "sqlite":
        return func.group_concat(column).label(alias)
    return func.array_agg(column).label(alias)


# ---------------------------
# MySQL JSON_TABLE compilation hook
# ---------------------------

class json_table(GenericFunction):
    inherit_cache = True


@compiles(json_table, "mysql")
def _compile_json_table(element, compiler, **kw):
    ddl_compiler = compiler.dialect.ddl_compiler(compiler.dialect, None)
    clauses = list(element.clauses)
    if len(clauses) < 2:
        raise ValueError("json_table requires (json_expr, column_definitions...)")
    json_expr = clauses[0]
    col_defs = clauses[1:]
    return "JSON_TABLE({}, '$[*]' COLUMNS({} PATH '$'))".format(
        compiler.process(json_expr, **kw),
        ",".join(ddl_compiler.process(CreateColumn(clause), **kw) for clause in col_defs),
    )


# ---------------------------
# Safer get_or_create
# ---------------------------

def get_or_create(
    session: Session,
    model: Type[T],
    defaults: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Tuple[T, bool]:
    """
    Get an instance by filter kwargs, or create one with those filters plus any defaults.

    Uses a nested transaction so an IntegrityError doesn't rollback unrelated work
    in the outer session (when supported by the dialect).
    """
    query = select(model)
    for key, value in kwargs.items():
        if not hasattr(model, key):
            raise AttributeError(f"{model.__name__} has no attribute {key!r}")
        query = query.where(getattr(model, key) == value)

    instance = session.exec(query).first()
    if instance:
        return instance, False

    create_attrs = dict(kwargs)
    if defaults:
        create_attrs.update(defaults)

    instance = model(**create_attrs)
    session.add(instance)

    try:
        # Nested transaction prevents nuking the whole session on conflict
        with session.begin_nested():
            session.flush()
        return instance, True
    except IntegrityError:
        # Someone else created it first; refresh view
        instance = session.exec(query).first()
        if instance:
            return instance, False
        raise


# ---------------------------
# Serialization helper
# ---------------------------

def custom_serialize(obj: Any) -> Any:
    """
    Custom serializer that handles Pydantic models and other complex types.
    """
    if isinstance(obj, dict):
        return {k: custom_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [custom_serialize(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(custom_serialize(item) for item in obj)
    if isinstance(obj, BaseModel):
        # Support pydantic v1 and v2
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return obj.dict()
    if isinstance(obj, Enum):
        return obj.value

    try:
        return jsonable_encoder(obj)
    except Exception:
        return str(obj)