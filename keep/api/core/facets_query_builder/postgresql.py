from sqlalchemy import Integer, String, case, cast, func, literal, select
from sqlalchemy.sql import literal_column
from sqlalchemy.dialects.postgresql import JSONB

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)


class PostgreSqlFacetsQueryBuilder(BaseFacetsQueryBuilder):

    def _cast_column(self, column, data_type: DataType):
        if data_type == DataType.BOOLEAN:
            return case(
                (func.lower(column) == "true", literal("true")),
                (cast(column, Integer) >= 1, literal("true")),
                (column != "", literal("true")),
                else_=literal("false"),
            )

        return super()._cast_column(column, data_type)

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

    def _build_facet_subquery_for_column(
        self, base_query, metadata: PropertyMetadataInfo
    ):
        coalecense_args = []

        for item in metadata.field_mappings:
            if isinstance(item, JsonFieldMapping):
                coalecense_args.append(self._handle_json_mapping(item))
            elif isinstance(metadata.field_mappings[0], SimpleFieldMapping):
                coalecense_args.append(self._handle_simple_mapping(item))

        return select(
            func.distinct(literal_column("entity_id")),
            cast(self._coalesce(coalecense_args), String).label("facet_value"),
        ).select_from(base_query)

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        all_columns = [field_mapping.json_prop] + [
            f"'{item}'" for item in field_mapping.prop_in_json
        ]

        json_property_path = " -> ".join(all_columns[:-1])
        return literal_column(f"({json_property_path}) ->> {all_columns[-1]}")
