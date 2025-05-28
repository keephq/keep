from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from keep.api.core.cel_to_sql.sql_providers.get_cel_to_sql_provider_for_dialect import (
    get_cel_to_sql_provider,
)
from keep.api.core.db import engine
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)
from keep.api.core.facets_query_builder.mysql import MySqlFacetsQueryBuilder
from keep.api.core.facets_query_builder.postgresql import PostgreSqlFacetsQueryBuilder
from keep.api.core.facets_query_builder.sqlite import SqliteFacetsHandler


def get_facets_query_builder(
    properties_metadata: PropertiesMetadata,
) -> BaseFacetsQueryBuilder:
    return get_facets_query_builder_for_dialect(
        engine.dialect.name, properties_metadata
    )


def get_facets_query_builder_for_dialect(
    dialect_name: str,
    properties_metadata: PropertiesMetadata,
) -> BaseFacetsQueryBuilder:
    if dialect_name == "sqlite":
        return SqliteFacetsHandler(
            properties_metadata, get_cel_to_sql_provider(properties_metadata)
        )
    elif dialect_name == "mysql":
        return MySqlFacetsQueryBuilder(
            properties_metadata, get_cel_to_sql_provider(properties_metadata)
        )
    elif dialect_name == "postgresql":
        return PostgreSqlFacetsQueryBuilder(
            properties_metadata, get_cel_to_sql_provider(properties_metadata)
        )

    else:
        raise ValueError(f"Unsupported dialect: {engine.dialect.name}")
