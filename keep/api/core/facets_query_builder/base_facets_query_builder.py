import hashlib
from typing import Any
from sqlalchemy import CTE, literal_column
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
from sqlalchemy import func, literal, literal_column, select, text


class BaseFacetsQueryBuilder:
    """
    Base class for facets handlers.
    """

    def __init__(
        self, properties_metadata: PropertiesMetadata, cel_to_sql: BaseCelToSqlProvider
    ):
        self.properties_metadata = properties_metadata
        self.cel_to_sql = cel_to_sql

    def build_facets_data_query(
        self,
        base_query_factory: lambda facet_property_path, involved_fields, select_statement: Any,
        entity_id_column: any,
        facets: list[FacetDto],
        facet_options_query: FacetOptionsQueryDto,
    ):
        """
        Builds a SQL query to extract and count facet data based on the provided parameters.

        Args:
            dialect (str): The SQL dialect to use (e.g., 'postgresql', 'mysql').
            base_query: The base SQLAlchemy query object to build upon.
            facets (list[FacetDto]): A list of facet data transfer objects specifying the facets to be queried.
            properties_metadata (PropertiesMetadata): Metadata about the properties to be used in the query.
            cel (str): A CEL (Common Expression Language) string to filter the base query.

        Returns:
            sqlalchemy.sql.Selectable: A SQLAlchemy selectable object representing the constructed query.
        """
        # Main Query: JSON Extraction and Counting
        union_queries = []

        # prevents duplicate queries for the same facet property path and its cel combination
        visited_facets = set()

        for facet in facets:
            facet_cel = facet_options_query.facet_queries.get(facet.id, "")
            facet_key = get_facet_key(
                facet_property_path=facet.property_path,
                filter_cel=facet_options_query.cel,
                facet_cel=facet_cel,
            )
            if facet_key in visited_facets:
                continue

            cel_queries = [
                facet_options_query.cel,
                facet_options_query.facet_queries.get(facet.id, None),
            ]
            final_cel = " && ".join(filter(lambda cel: cel, cel_queries))

            facet_sub_query = self.build_facet_subquery(
                facet_key=facet_key,
                entity_id_column=entity_id_column,
                base_query_factory=base_query_factory,
                facet_property_path=facet.property_path,
                facet_cel=final_cel,
            )

            union_queries.append(facet_sub_query)
            visited_facets.add(facet_key)

        query = None

        if len(union_queries) > 1:
            query = union_queries[0].union_all(*union_queries[1:])
        else:
            query = union_queries[0]

        return query

    def build_facet_select(self, entity_id_column, facet_key: str, facet_property_path):
        property_metadata = self.properties_metadata.get_property_metadata_for_str(
            facet_property_path
        )

        return [
            literal(facet_key).label("facet_id"),
            self._get_select_for_column(property_metadata).label("facet_value"),
            func.count(func.distinct(entity_id_column)).label("matches_count"),
        ]

    def build_facet_subquery(
        self,
        facet_key: str,
        entity_id_column,
        base_query_factory: lambda facet_property_path, involved_fields, select_statement: Any,
        facet_property_path: str,
        facet_cel: str,
    ):
        metadata = self.properties_metadata.get_property_metadata_for_str(
            facet_property_path
        )

        involved_fields = []
        sql_filter = None

        if facet_cel:
            cel_to_sql_result = self.cel_to_sql.convert_to_sql_str_v2(facet_cel)
            involved_fields = cel_to_sql_result.involved_fields
            sql_filter = cel_to_sql_result.sql

        base_query = base_query_factory(
            facet_property_path,
            involved_fields,
            self.build_facet_select(
                entity_id_column=entity_id_column,
                facet_property_path=facet_property_path,
                facet_key=facet_key,
            ),
        )

        if sql_filter:
            base_query = base_query.filter(text(sql_filter))

        if metadata.data_type == DataType.ARRAY:
            facet_source_subquery = self._build_facet_subquery_for_json_array(
                base_query,
                metadata,
            )
        else:
            facet_source_subquery = self._build_facet_subquery_for_column(
                base_query,
                metadata,
            )

        if isinstance(facet_source_subquery, CTE):
            return select(
                literal_column("facet_id"),
                literal_column("facet_value"),
                literal_column("matches_count"),
            ).select_from(facet_source_subquery)

        return facet_source_subquery.group_by(
            literal_column("facet_id"), literal_column("facet_value")
        )

    def _get_select_for_column(self, property_metadata: PropertyMetadataInfo):
        coalecense_args = []
        should_cast = False

        for field_mapping in property_metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                should_cast = True
                coalecense_args.append(self._handle_json_mapping(field_mapping))
            elif isinstance(field_mapping, SimpleFieldMapping):
                coalecense_args.append(self._handle_simple_mapping(field_mapping))
            select_expression = self._coalesce(coalecense_args)

        if should_cast:
            return self._cast_column(select_expression, property_metadata.data_type)

        return select_expression

    def _cast_column(
        self,
        column,
        data_type: DataType,
    ):
        return column

    def _build_facet_subquery_for_column(
        self, base_query, metadata: PropertyMetadataInfo
    ):
        # coalecense_args = []

        # for item in metadata.field_mappings:
        #     if isinstance(item, JsonFieldMapping):
        #         coalecense_args.append(self._handle_json_mapping(item))
        #     elif isinstance(metadata.field_mappings[0], SimpleFieldMapping):
        #         coalecense_args.append(self._handle_simple_mapping(item))

        return base_query

        # return select(
        #     func.distinct(literal_column("entity_id")),
        #     self._coalesce(coalecense_args).label("facet_value"),
        # ).select_from(base_query)

    def _build_facet_subquery_for_json_array(
        self,
        base_query,
        metadata: PropertyMetadataInfo,
    ):
        raise NotImplementedError("This method should be implemented in subclasses.")

    def _handle_simple_mapping(self, field_mapping: SimpleFieldMapping):
        return literal_column(field_mapping.map_to)

    def _coalesce(self, args: list):
        if len(args) == 1:
            return args[0]

        return func.coalesce(*args)

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        raise NotImplementedError("This method should be implemented in subclasses.")
