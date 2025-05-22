from sqlalchemy import Integer, case, cast, func, literal, literal_column, select

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)


class SqliteFacetsHandler(BaseFacetsQueryBuilder):

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
        json_table_join = func.json_each(literal_column(column_name)).table_valued(
            "value"
        )
        return select(
            func.distinct(base_query.c.entity_id),
            json_table_join.c.value.label("facet_value"),
        ).select_from(base_query, json_table_join)

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        built_json_path = "$." + ".".join(
            [f'"{item}"' for item in field_mapping.prop_in_json]
        )
        return func.json_extract(
            literal_column(field_mapping.json_prop), built_json_path
        )
