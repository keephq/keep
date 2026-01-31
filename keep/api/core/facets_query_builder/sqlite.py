from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, case, cast, func, literal, literal_column, true
from sqlalchemy.sql import ColumnElement

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import (
    BaseFacetsQueryBuilder,
)


class SqliteFacetsHandler(BaseFacetsQueryBuilder):
    ARRAY_VALUE_COL = "value"

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        if property_metadata.data_type == DataType.ARRAY:
            alias = self._array_alias(property_metadata.field_name)
            # alias.value
            return literal_column(f"{alias}.{self.ARRAY_VALUE_COL}")

        return super()._get_select_for_column(property_metadata)

    def _cast_column(self, column: ColumnElement[Any], data_type: DataType):
        if data_type != DataType.BOOLEAN:
            return super()._cast_column(column, data_type)

        # Normalize as text
        col_txt = cast(column, String)
        col_norm = func.lower(func.trim(col_txt))

        return case(
            (column.is_(None), literal("false")),
            (col_norm.in_(["false", "0", "no", "n", "off", ""]), literal("false")),
            (col_norm.in_(["true", "1", "yes", "y", "on"]), literal("true")),
            # Numeric-ish values: >=1 true, else false
            (cast(col_norm, Integer) >= 1, literal("true")),
            else_=literal("false"),
        )

    def _build_facet_subquery_for_json_array(self, base_query: Any, metadata: PropertyMetadataInfo):
        source_col = self._get_array_source_column(metadata)
        alias = self._array_alias(metadata.field_name)

        # json_each(<json>) returns table columns including "value"
        # We alias it so facet_value can reference alias.value.
        json_each_tvf = func.json_each(literal_column(source_col)).table_valued(self.ARRAY_VALUE_COL)
        return base_query.outerjoin(json_each_tvf.alias(alias), true())

    def _get_array_source_column(self, metadata: PropertyMetadataInfo) -> str:
        if not metadata.field_mappings:
            raise ValueError(f"No field mappings for array facet: {metadata.field_name}")

        for m in metadata.field_mappings:
            if isinstance(m, SimpleFieldMapping):
                return m.map_to

        raise ValueError(
            f"Array facet {metadata.field_name} has no SimpleFieldMapping; cannot expand JSON array."
        )

    def _array_alias(self, field_name: str) -> str:
        # Keep underscores to avoid collisions.
        return f"{field_name}_array"

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        # Build $.\"a\".\"b\" for keys with special chars
        built_json_path = "$." + ".".join([f'"{item}"' for item in field_mapping.prop_in_json])

        # SQLite json_extract may return typed JSON values; cast to text for stable facet display.
        return cast(func.json_extract(literal_column(field_mapping.json_prop), built_json_path), String)