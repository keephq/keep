from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.db import engine
from keep.api.core.facets_handler.base_facets_handler import BaseFacetsHandler
from keep.api.core.facets_handler.mysql import MySqlFacetsHandler
from keep.api.core.facets_handler.postgresql import PostgreSqlFacetsHandler
from keep.api.core.facets_handler.sqlite import SqliteFacetsHandler


def get_facets_handler(
    properties_metadata: PropertiesMetadata,
) -> BaseFacetsHandler:
    return get_facets_handler_for_dialect(engine.dialect.name, properties_metadata)


def get_facets_handler_for_dialect(
    dialect_name: str,
    properties_metadata: PropertiesMetadata,
) -> BaseFacetsHandler:
    if dialect_name == "sqlite":
        return SqliteFacetsHandler(properties_metadata)
    elif dialect_name == "mysql":
        return MySqlFacetsHandler(properties_metadata)
    elif dialect_name == "postgresql":
        return PostgreSqlFacetsHandler(properties_metadata)

    else:
        raise ValueError(f"Unsupported dialect: {engine.dialect.name}")
