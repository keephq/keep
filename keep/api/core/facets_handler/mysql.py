from sqlalchemy import func, literal_column

from keep.api.core.cel_to_sql.properties_metadata import JsonFieldMapping
from keep.api.core.facets_handler.base_facets_handler import BaseFacetsHandler


class MySqlFacetsHandler(BaseFacetsHandler):
    def _handle_json_mapping(self, field_mapping: JsonFieldMapping):
        built_json_path = "$." + ".".join(
            [f'"{item}"' for item in field_mapping.prop_in_json]
        )
        return func.json_unquote(
            func.json_extract(literal_column(field_mapping.json_prop), built_json_path)
        )
