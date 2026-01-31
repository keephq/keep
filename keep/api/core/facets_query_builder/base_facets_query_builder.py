from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import CTE, func, literal, literal_column, select, text
from sqlalchemy.sql import ColumnElement

from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertiesMetadata,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider
from keep.api.core.facets_query_builder.utils import get_facet_key
from keep.api.models.facet import FacetDto, FacetOptionsQueryDto


# A "factory" that returns some SQLAlchemy query-ish object that supports `.filter()`
# and can be unioned (ORM Query or Selectable, depending on your codebase).
BaseQueryFactory = Callable[
    [str, Sequence[str], Sequence[ColumnElement[Any]]],
    Any,
]


class BaseFacetsQueryBuilder:
    """
    Base class for facets handlers.
    """

    def __init__(
        self,
        properties_metadata: PropertiesMetadata,
        cel_to_sql: BaseCelToSqlProvider,
    ):
        self.properties_metadata = properties_metadata
        self.cel_to_sql = cel_to_sql

    def build_facets_data_query(
        self,
        base_query_factory: BaseQueryFactory,
        entity_id_column: Any,
        facets: list[FacetDto],
        facet_options_query: FacetOptionsQueryDto,
    ):
        """
        Builds a SQL query to extract and count facet data based on the provided parameters.

        Returns:
            A SQLAlchemy selectable/query representing a UNION ALL over requested facets.
        """
        union_queries: list[Any] = []
        visited_facets: Set[str] = set()

        if not facets:
            # Return an empty result with the correct shape.
            # This avoids IndexError and keeps downstream consumers happy.
            return (
                select(
                    literal("").label("facet_id"),
                    literal_column("NULL").label("facet_value"),
                    literal(0).label("matches_count"),
                )
                .where(text("1=0"))
            )

        base_filter_cel = facet_options_query.cel or ""

        for facet in facets:
            facet_specific_cel = facet_options_query.facet_queries.get(facet.id) or ""

            facet_key = get_facet_key(
                facet_property_path=facet.property_path,
                filter_cel=base_filter_cel,
                facet_cel=facet_specific_cel,
            )

            # Deduplicate identical (property_path + combined CEL) facets
            if facet_key in visited_facets:
                continue

            final_cel = self._combine_cel(base_filter_cel, facet_specific_cel)

            facet_sub_query = self.build_facet_subquery(
                facet_key=facet_key,
                entity_id_column=entity_id_column,
                base_query_factory=base_query_factory,
                facet_property_path=facet.property_path,
                facet_cel=final_cel,
            )

            union_queries.append(facet_sub_query)
            visited_facets.add(facet_key)

        # If everything got deduped away (possible), return empty shape.
        if not union_queries:
            return (
                select(
                    literal("").label("facet_id"),
                    literal_column("NULL").label("facet_value"),
                    literal(0).label("matches_count"),
                )
                .where(text("1=0"))
            )

        if len(union_queries) == 1:
            return union_queries[0]

        return union_queries[0].union_all(*union_queries[1:])

    def build_facet_select(
        self,
        entity_id_column: Any,
        facet_key: str,
        facet_property_path: str,
    ) -> list[ColumnElement[Any]]:
        property_metadata = self.properties_metadata.get_property_metadata_for_str(
            facet_property_path
        )

        facet_id_expr = literal(facet_key).label("facet_id")
        facet_value_expr = self._get_select_for_column(property_metadata).label(
            "facet_value"
        )
        matches_count_expr = func.count(func.distinct(entity_id_column)).label(
            "matches_count"
        )

        return [facet_id_expr, facet_value_expr, matches_count_expr]

    def build_facet_subquery(
        self,
        facet_key: str,
        entity_id_column: Any,
        base_query_factory: BaseQueryFactory,
        facet_property_path: str,
        facet_cel: str,
    ):
        metadata = self.properties_metadata.get_property_metadata_for_str(
            facet_property_path
        )

        involved_fields: Sequence[str] = ()
        sql_filter: Optional[str] = None

        if facet_cel:
            cel_to_sql_result = self.cel_to_sql.convert_to_sql_str_v2(facet_cel)
            involved_fields = cel_to_sql_result.involved_fields or ()
            sql_filter = cel_to_sql_result.sql

        select_cols = self.build_facet_select(
            entity_id_column=entity_id_column,
            facet_property_path=facet_property_path,
            facet_key=facet_key,
        )

        base_query = base_query_factory(
            facet_property_path,
            involved_fields,
            select_cols,
        )

        if sql_filter:
            # NOTE: This is still raw SQL text.
            # If convert_to_sql_str_v2 ever inlines user literals, that’s a problem.
            # Next upgrade would be: return (sql, params) and bind them here safely.
            base_query = base_query.filter(text(sql_filter))

        if metadata.data_type == DataType.ARRAY:
            facet_source = self._build_facet_subquery_for_json_array(
                base_query,
                metadata,
            )
        else:
            facet_source = base_query

        # If array handler returns a CTE, assume it already includes the 3 labeled columns.
        if isinstance(facet_source, CTE):
            return select(
                literal_column("facet_id"),
                literal_column("facet_value"),
                literal_column("matches_count"),
            ).select_from(facet_source)

        # Prefer grouping by the actual expressions when possible.
        # We rely on labels existing, but avoid brittle string group_by where we can.
        # For ORM Query, group_by needs expressions; for some query flavors, label refs work.
        return facet_source.group_by(
            literal_column("facet_id"),
            literal_column("facet_value"),
        )

    def _get_select_for_column(
        self,
        property_metadata: PropertyMetadataInfo,
    ) -> ColumnElement[Any]:
        """
        Build the SELECT expression for a facet value based on property field mappings.

        - Coalesces multiple mappings.
        - Casts when JSON mappings are present.
        - Returns NULL if no mappings exist (safer than exploding).
        """
        coalesce_args: list[ColumnElement[Any]] = []
        should_cast = False

        for field_mapping in property_metadata.field_mappings or []:
            if isinstance(field_mapping, JsonFieldMapping):
                should_cast = True
                coalesce_args.append(self._handle_json_mapping(field_mapping))
            elif isinstance(field_mapping, SimpleFieldMapping):
                coalesce_args.append(self._handle_simple_mapping(field_mapping))

        if not coalesce_args:
            select_expression: ColumnElement[Any] = literal_column("NULL")
        else:
            select_expression = self._coalesce(coalesce_args)

        if should_cast:
            return self._cast_column(select_expression, property_metadata.data_type)

        return select_expression

    def _cast_column(
        self,
        column: ColumnElement[Any],
        data_type: DataType,
    ) -> ColumnElement[Any]:
        # Subclasses can override and cast per dialect/type.
        return column

    def _build_facet_subquery_for_json_array(
        self,
        base_query: Any,
        metadata: PropertyMetadataInfo,
    ):
        raise NotImplementedError("This method should be implemented in subclasses.")

    def _handle_simple_mapping(
        self,
        field_mapping: SimpleFieldMapping,
    ) -> ColumnElement[Any]:
        return literal_column(field_mapping.map_to)

    def _coalesce(self, args: Sequence[ColumnElement[Any]]) -> ColumnElement[Any]:
        if len(args) == 1:
            return args[0]
        return func.coalesce(*args)

    def _handle_json_mapping(
        self,
        field_mapping: JsonFieldMapping,
    ) -> ColumnElement[Any]:
        raise NotImplementedError("This method should be implemented in subclasses.")

    def _combine_cel(self, base_cel: str, facet_cel: str) -> str:
        """
        Combine CEL filters into a single CEL expression.
        """
        parts = [p.strip() for p in (base_cel or "", facet_cel or "") if p and p.strip()]
        return " && ".join(parts)