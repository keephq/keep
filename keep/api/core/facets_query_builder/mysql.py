from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from sqlalchemy import (
    Integer,
    String,
    case,
    cast,
    func,
    literal,
    literal_column,
    text,
    true,
)
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

BaseQueryFactory = Callable[[str, Sequence[str], Sequence[ColumnElement[Any]]], Any]


class MySqlFacetsQueryBuilder(BaseFacetsQueryBuilder):
    FACET_LIMIT = 50
    ARRAY_VALUE_COL = "value"  # JSON_TABLE column name

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

        # Deterministic results. Prefer most common values first, then stable tie-break.
        # Note: "matches_count" label exists in the base builder's select list.
        return (
            q.order_by(literal_column("matches_count").desc(), literal_column("facet_value"))
            .limit(self.FACET_LIMIT)
        )

    def _cast_column(self, column: ColumnElement[Any], data_type: DataType):
        if data_type != DataType.BOOLEAN:
            return super()._cast_column(column, data_type)

        # Normalize: lower(trim(col))
        col = func.lower(func.trim(column))

        # MySQL treats many things as true-y. We make it explicit and predictable.
        # - true: "true", "1", "yes", "y", "on"
        # - false: "false", "0", "no", "n", "off", "", NULL
        return case(
            (column.is_(None), literal("false")),
            (col.in_(["false", "0", "no", "n", "off", ""]), literal("false")),
            (col.in_(["true", "1", "yes", "y", "on"]), literal("true")),
            # If it casts to int >=1 treat as true; if cast fails, MySQL often returns 0.
            (cast(column, Integer) >= 1, literal("true")),
            else_=literal("false"),
        )

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        # For ARRAY facets, the array handler creates a CTE with facet_value already computed.
        # So here we keep default behavior and let array CTE define facet_value.
        # If your base_query_factory depends on a specific label, keep it consistent here.
        return super()._get_select_for_column(property_metadata)

    def _build_facet_subquery_for_json_array(self, base_query: Any, metadata: PropertyMetadataInfo):
        """
        Expand a JSON array column into rows using JSON_TABLE, then group and CTE it.

        Assumes MySQL 8.0+ for JSON_TABLE.
        """
        source_col = self._get_array_source_column(metadata)

        # Build JSON_TABLE as raw SQL because SQLAlchemy doesn't natively model the full
        # JSON_TABLE (... COLUMNS (...)) clause cleanly across versions.
        #
        # JSON_TABLE(<json_doc>, '$[*]' COLUMNS (value VARCHAR(127) PATH '$')) AS jt
        jt_sql = text(
            f"JSON_TABLE({source_col}, '$[*]' "
            f"COLUMNS ({self.ARRAY_VALUE_COL} VARCHAR(127) PATH '$'))"
        ).columns(**{self.ARRAY_VALUE_COL: String(127)})

        jt = jt_sql.alias(f"{metadata.field_name}_jt")

        # Join the table function. ON TRUE means "for each row expand array elements".
        q = base_query.outerjoin(jt, true())

        # Override facet_value to come from JSON_TABLE value.
        # We rely on base_query selecting facet_id and matches_count labels already.
        q = q.with_entities(
            literal_column("facet_id").label("facet_id"),
            literal_column(f"{jt.name}.{self.ARRAY_VALUE_COL}").label("facet_value"),
            literal_column("matches_count").label("matches_count"),
        )

        # Group and CTE with safe name
        cte_name = f"{metadata.field_name}_facet_array"
        return q.group_by(literal_column("facet_id"), literal_column("facet_value")).cte(cte_name)

    def _get_array_source_column(self, metadata: PropertyMetadataInfo) -> str:
        """
        Pick a concrete SQL column name for the JSON array source.
        Prefer SimpleFieldMapping; if missing, fail loudly.
        """
        if not metadata.field_mappings:
            raise ValueError(f"No field mappings for array facet: {metadata.field_name}")

        for m in metadata.field_mappings:
            if isinstance(m, SimpleFieldMapping):
                return m.map_to

        raise ValueError(
            f"Array facet {metadata.field_name} has no SimpleFieldMapping; "
            f"cannot JSON_TABLE a non-column mapping."
        )

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        # Build $.\"a\".\"b\" style paths to handle keys with special chars safely.
        built_json_path = "$." + ".".join([f'"{item}"' for item in field_mapping.prop_in_json])

        return func.json_unquote(
            func.json_extract(literal_column(field_mapping.json_prop), built_json_path)
        )