from typing import Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    case,
    cast,
    func,
    literal,
    literal_column,
    select,
)
from sqlmodel import true

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)


class MySqlFacetsQueryBuilder(BaseFacetsQueryBuilder):

    def build_facet_subquery(
        self,
        entity_id_column,
        base_query_factory: lambda facet_property_path, involved_fields, select_statement: Any,
        facet_property_path: str,
        facet_cel: str,
    ):
        return (
            super()
            .build_facet_subquery(
                entity_id_column=entity_id_column,
                base_query_factory=base_query_factory,
                facet_property_path=facet_property_path,
                facet_cel=facet_cel,
            )
            .limit(50)
        )

    def _cast_column(self, column, data_type: DataType):
        if data_type == DataType.BOOLEAN:
            return case(
                (func.lower(column) == "true", literal("true")),
                (cast(column, Integer) >= 1, literal("true")),
                (column != "", literal("true")),
                else_=literal("false"),
            )

        return super()._cast_column(column, data_type)

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        if property_metadata.data_type == DataType.ARRAY:
            return literal_column(property_metadata.field_name + "_array").collate(
                "utf8mb4_0900_ai_ci"
            )
        return super()._get_select_for_column(property_metadata)

    def _build_facet_subquery_for_json_array(
        self, base_query, metadata: PropertyMetadataInfo
    ):
        column_name = metadata.field_mappings[0].map_to

        json_table_join = func.json_table(
            literal_column(column_name),
            Column(metadata.field_name + "_array", String(127)),
        ).table_valued("value")

        base_query = base_query.outerjoin(json_table_join, true())

        return base_query.group_by(
            literal_column("facet_id"), literal_column("facet_value")
        ).cte(f"{column_name}_facet_subquery")

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        built_json_path = "$." + ".".join(
            [f'"{item}"' for item in field_mapping.prop_in_json]
        )
        return func.json_unquote(
            func.json_extract(literal_column(field_mapping.json_prop), built_json_path)
        )
