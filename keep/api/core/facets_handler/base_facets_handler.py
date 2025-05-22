from sqlalchemy import literal_column
from keep.api.core.cel_to_sql.ast_nodes import DataType
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    JsonFieldMapping,
    PropertiesMetadata,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider
from keep.api.models.facet import FacetDto
from sqlalchemy import func, literal, literal_column, select, text


class BaseFacetsHandler:
    """
    Base class for facets handlers.
    """

    def __init__(
        self, properties_metadata: PropertiesMetadata, cel_to_sql: BaseCelToSqlProvider
    ):
        self.properties_metadata = properties_metadata
        self.cel_to_sql = cel_to_sql

    def build_facet_selects(self, facets: list[FacetDto]):
        new_fields_config: list[FieldMappingConfiguration] = []
        select_expressions = {}

        for facet in facets:
            property_metadata = self.properties_metadata.get_property_metadata_for_str(
                facet.property_path
            )
            if property_metadata is None:
                continue

            select_field = ("facet_" + facet.property_path.replace(".", "_")).lower()

            new_fields_config.append(
                FieldMappingConfiguration(
                    map_from_pattern=facet.property_path,
                    map_to=[select_field],
                    data_type=property_metadata.data_type,
                )
            )
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
                select_expression = self._cast_column(
                    select_expression, property_metadata.data_type
                )

            select_expressions[select_field] = select_expression.label(select_field)

        return {
            "new_fields_config": new_fields_config,
            "select_expressions": list(select_expressions.values()),
        }

    def build_facet_subquery(
        self, base_query, facet_key: str, facet_property_path: str, facet_cel: str
    ):
        metadata = self.properties_metadata.get_property_metadata_for_str(
            facet_property_path
        )

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

        facet_source_subquery = facet_source_subquery.filter(
            text(self.cel_to_sql.convert_to_sql_str(facet_cel))
        )

        return (
            select(
                literal(facet_key).label("facet_id"),
                literal_column("facet_value"),
                func.count().label("matches_count"),
            )
            .select_from(facet_source_subquery)
            .group_by(literal_column("facet_id"), literal_column("facet_value"))
        )

    def _cast_column(
        self,
        column,
        data_type: DataType,
    ):
        return column

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
            self._coalesce(coalecense_args).label("facet_value"),
        ).select_from(base_query)

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
