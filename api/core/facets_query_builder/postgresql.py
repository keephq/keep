from typing import Any
from sqlalchemy import Integer, String, case, cast, func, lateral, literal, select
from sqlalchemy.sql import literal_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import true

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)


class PostgreSqlFacetsQueryBuilder(BaseFacetsQueryBuilder):

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        if property_metadata.data_type == DataType.ARRAY:
            return literal_column(
                f'"{property_metadata.field_name.replace("_", "")}_array".value'
            )

        if property_metadata.data_type == DataType.UUID:
            return cast(super()._get_select_for_column(property_metadata), String)

        if next(
            (
                True
                for item in property_metadata.field_mappings
                if not isinstance(item, JsonFieldMapping)
            ),
            False,
        ):
            return cast(super()._get_select_for_column(property_metadata), String)

        return super()._get_select_for_column(property_metadata)

    def build_facet_subquery(
        self,
        facet_key: str,
        entity_id_column,
        base_query_factory: lambda facet_property_path, involved_fields, select_statement: Any,
        facet_property_path: str,
        facet_cel: str,
    ):
        return (
            super()
            .build_facet_subquery(
                facet_key=facet_key,
                entity_id_column=entity_id_column,
                base_query_factory=base_query_factory,
                facet_property_path=facet_property_path,
                facet_cel=facet_cel,
            )
            .limit(50)  # Limit number of returned options per facet by 50
        )

    def _cast_column(self, column, data_type: DataType):
        if data_type == DataType.BOOLEAN:
            return case(
                (func.lower(column) == "true", literal("true")),
                (func.lower(column) == "false", literal("false")),
                (
                    column.op("~")("^[0-9]+$"),
                    case(
                        (cast(column, Integer) >= 1, literal("true")),
                        else_=literal("false"),
                    ),
                ),
                (column != "", literal("true")),
                else_=literal("false"),
            )

        return super()._cast_column(column, data_type)

    def _build_facet_subquery_for_json_array(
        self, base_query, metadata: PropertyMetadataInfo
    ):
        column_name = metadata.field_mappings[0].map_to
        alias = metadata.field_name.replace("_", "") + "_array"
        json_table_join = lateral(
            (
                select(
                    func.jsonb_array_elements_text(
                        cast(literal_column(column_name), JSONB)
                    ).label("value")
                )
            )
        )
        return base_query.outerjoin(json_table_join.alias(alias), true())

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        all_columns = [field_mapping.json_prop] + [
            f"'{item}'" for item in field_mapping.prop_in_json
        ]

        json_property_path = " -> ".join(all_columns[:-1])
        return literal_column(f"({json_property_path}) ->> {all_columns[-1]}")
