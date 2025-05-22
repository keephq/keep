from sqlalchemy.sql import literal_column

from keep.api.core.cel_to_sql.properties_metadata import JsonFieldMapping
from keep.api.core.facets_handler.base_facets_handler import BaseFacetsHandler


class PostgreSqlFacetsHandler(BaseFacetsHandler):
    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        all_columns = [field_mapping.json_prop] + [
            f"'{item}'" for item in field_mapping.prop_in_json
        ]

        json_property_path = " -> ".join(all_columns[:-1])
        return literal_column(f"({json_property_path}) ->> {all_columns[-1]}")
