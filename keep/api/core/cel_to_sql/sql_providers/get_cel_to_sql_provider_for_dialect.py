from __future__ import annotations

from typing import Callable, Mapping, Type

from sqlalchemy.engine.interfaces import Dialect

from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider
from keep.api.core.cel_to_sql.sql_providers.postgresql import CelToPostgreSqlProvider
from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider
from keep.api.core.cel_to_sql.sql_providers.mysql import CelToMySqlProvider
from keep.api.core.db import engine


# Dialect aliases humans love to invent.
_DIALECT_ALIASES: Mapping[str, str] = {
    "postgres": "postgresql",
    "postgre": "postgresql",
    "psql": "postgresql",
}

# Registry keeps the selection logic tidy.
_PROVIDER_REGISTRY: Mapping[str, Type[BaseCelToSqlProvider]] = {
    "sqlite": CelToSqliteProvider,
    "mysql": CelToMySqlProvider,
    "postgresql": CelToPostgreSqlProvider,
}


def _normalize_dialect_name(dialect_name: str) -> str:
    name = (dialect_name or "").strip().lower()
    return _DIALECT_ALIASES.get(name, name)


def get_cel_to_sql_provider(properties_metadata: PropertiesMetadata) -> BaseCelToSqlProvider:
    """
    Convenience wrapper using the application's default global engine.
    """
    return get_cel_to_sql_provider_for_dialect(engine.dialect, properties_metadata)


def get_cel_to_sql_provider_for_dialect(
    dialect: str | Dialect,
    properties_metadata: PropertiesMetadata,
) -> BaseCelToSqlProvider:
    """
    Create a CEL→SQL provider for a given SQLAlchemy dialect (or dialect name).
    This function avoids relying on global engine state (except through the convenience wrapper).
    """
    if properties_metadata is None:
        raise ValueError("properties_metadata must not be None")

    if isinstance(dialect, str):
        dialect_name = _normalize_dialect_name(dialect)
        # If only a name is provided, we still need a Dialect instance for literal processors.
        # Caller should prefer passing a Dialect; we fall back to global engine for compatibility.
        dialect_obj = engine.dialect
    else:
        dialect_obj = dialect
        dialect_name = _normalize_dialect_name(getattr(dialect_obj, "name", ""))

    provider_cls = _PROVIDER_REGISTRY.get(dialect_name)
    if not provider_cls:
        supported = ", ".join(sorted(_PROVIDER_REGISTRY.keys()))
        raise ValueError(f"Unsupported dialect: {dialect_name}. Supported: {supported}")

    return provider_cls(dialect_obj, properties_metadata)