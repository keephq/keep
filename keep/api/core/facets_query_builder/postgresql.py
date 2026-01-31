from __future__ import annotations

from typing import Any, Callable, Sequence

from sqlalchemy import Integer, String, case, cast, func, lateral, literal, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import ColumnElement, literal_column

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from keep.api.core.facets_query_builder.base_facets_query_builder import BaseFacetsQueryBuilder

BaseQueryFactory = Callable[[str, Sequence[str], Sequence[ColumnElement[Any]]], Any]


class PostgreSqlFacetsQueryBuilder(BaseFacetsQueryBuilder):
    FACET_LIMIT = 50
    ARRAY_VALUE_COL = "value"

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        # ARRAY facet values come from the lateral join alias created in _build_facet_subquery_for_json_array.
        if property_metadata.data_type == DataType.ARRAY:
            alias = self._array_alias(property_metadata.field_name)
            return literal_column(f'"{alias}".{self.ARRAY_VALUE_COL}')

        # Normalize UUIDs to string for facet display & grouping stability
        if property_metadata.data_type == DataType.UUID:
            return cast(super()._get_select_for_column(property_metadata), String)

        # If any mapping is non-JSON, cast to string to keep facet_value consistent
        has_non_json_mapping = any(
            not isinstance(m, JsonFieldMapping) for m in (property_metadata.field_mappings or [])
        )
        if has_non_json_mapping:
            return cast(super()._get_select_for_column(property_metadata), String)

        return super()._get_select_for_column(property_metadata)

    def build_facet_subquery(
        self,
        facet_key: str,
        entity_id_column: Any,
        base_query_factory: BaseQueryFactory,
        facet_property_path: str,
        facet_cel: str,
    ):
        q = super().build_facet_subquery(
            facet_key=facet_key,
            entity_id_column=entity_id_column,
            base_query_factory=base_query_factory,
            facet_property_path=facet_property_path,
            facet_cel=facet_cel,
        )

        # Deterministic facet option selection
        return (
            q.order_by(literal_column("matches_count").desc(), literal_column("facet_value"))
            .limit(self.FACET_LIMIT)
        )

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
            # purely numeric string
            (
                col_norm.op("~")("^[0-9]+$"),
                case(
                    (cast(col_norm, Integer) >= 1, literal("true")),
                    else_=literal("false"),
                ),
            ),
            else_=literal("false"),
        )

    def _build_facet_subquery_for_json_array(self, base_query: Any, metadata: PropertyMetadataInfo):
        source_col = self._get_array_source_column(metadata)
        alias = self._array_alias(metadata.field_name)

        # LATERAL (SELECT jsonb_array_elements_text(col::jsonb) AS value) AS <alias>
        lateral_subq = lateral(
            select(
                func.jsonb_array_elements_text(
                    cast(literal_column(source_col), JSONB)
                ).label(self.ARRAY_VALUE_COL)
            )
        ).alias(alias)

        # Join expanded array values
        return base_query.outerjoin(lateral_subq, true())

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
        # Keep underscores to avoid collisions and stay readable.
        return f"{field_name}_array"

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        """
        Safer JSONB path extraction:
        jsonb_extract_path_text(col::jsonb, 'a', 'b', ...)
        """
        # Cast JSON prop to JSONB if needed (depends on storage type).
        json_col = cast(literal_column(field_mapping.json_prop), JSONB)

        # jsonb_extract_path_text(json_col, 'k1', 'k2', ...)
        keys = [literal(k) for k in field_mapping.prop_in_json]
        return func.jsonb_extract_path_text(json_col, *keys)