from sqlalchemy import literal_column
from keep.api.core.cel_to_sql.properties_metadata import (
    FieldMappingConfiguration,
    JsonFieldMapping,
    PropertiesMetadata,
    SimpleFieldMapping,
)
from keep.api.models.facet import FacetDto
from sqlalchemy import Column, String, cast, func, literal, literal_column, select, text


class BaseFacetsHandler:
    """
    Base class for facets handlers.
    """

    def __init__(self, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata

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

            for field_mapping in property_metadata.field_mappings:
                if isinstance(field_mapping, JsonFieldMapping):
                    coalecense_args.append(self._handle_json_mapping(field_mapping))
                elif isinstance(field_mapping, SimpleFieldMapping):
                    coalecense_args.append(self._handle_simple_mapping(field_mapping))

            select_expressions[select_field] = (
                self._coalesce(coalecense_args)
                if len(coalecense_args) > 1
                else coalecense_args[0]
            ).label(select_field)

        return {
            "new_fields_config": new_fields_config,
            "select_expressions": list(select_expressions.values()),
        }

    def _handle_simple_mapping(self, field_mapping: SimpleFieldMapping):
        return literal_column(field_mapping.map_to)

    def _coalesce(self, args: list):
        return func.coalesce(*args)

    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        raise NotImplementedError("This method should be implemented in subclasses.")
