from sqlalchemy import cast, func, select
from sqlalchemy.sql import literal_column
from sqlalchemy.dialects.postgresql import JSONB

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
)
from keep.api.core.facets_handler.base_facets_handler import BaseFacetsHandler


class PostgreSqlFacetsHandler(BaseFacetsHandler):

    def _build_facet_subquery_for_json_array(
        self, base_query, metadata: PropertyMetadataInfo
    ):
        column_name = metadata.field_mappings[0].map_to
        json_table_join = func.jsonb_array_elements_text(
            cast(literal_column(column_name), JSONB)
        ).table_valued("value")
        return select(
            func.distinct(base_query.c.entity_id),
            json_table_join.c.value.label("facet_value"),
        ).select_from(base_query, json_table_join)

    def _handle_json_mapping(
        self, field_mapping: JsonFieldMapping, data_type: DataType
    ):
        all_columns = [field_mapping.json_prop] + [
            f"'{item}'" for item in field_mapping.prop_in_json
        ]

        json_property_path = " -> ".join(all_columns[:-1])
        return literal_column(f"({json_property_path}) ->> {all_columns[-1]}")
