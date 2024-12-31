from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToSqliteProvider(BaseCelToSqlProvider):
    def __init__(self, known_fields_mapping: dict):
        super().__init__()
        self.known_fields_mapping = known_fields_mapping

    def _visit_property(self, property_path: str):
        if property_path in self.known_fields_mapping:
            property_redirect = self.known_fields_mapping[property_path]
            field = property_redirect.get("field")
            return field

        if "*" in self.known_fields_mapping:
            json_redirect = self.known_fields_mapping["*"]
            field = json_redirect.get("field")       
            return f"json_extract({field}, \"$.{property_path}\")"
        
        return super()._visit_property(property_path)
    
    def _visit_contains_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path in self.known_fields_mapping:
            property_redirect = self.known_fields_mapping[property_path]
            field = property_redirect.get("field")
            return f"{field} LIKE \"%{method_args[0]}%\""

        if "*" in self.known_fields_mapping:
            json_redirect = self.known_fields_mapping["*"]
            field = json_redirect.get("field")        
            return f"json_extract({field}, \"$.{property_path}\") LIKE \"%{method_args[0]}%\""

        return f"{property_path} LIKE \"%{method_args[0]}%\""
    
    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path in self.known_fields_mapping:
            property_redirect = self.known_fields_mapping[property_path]
            field = property_redirect.get("field")
            return f"{field} LIKE \"{method_args[0]}%\""

        if "*" in self.known_fields_mapping:
            json_redirect = self.known_fields_mapping["*"]
            field = json_redirect.get("field")        
            return f"json_extract({field}, \"$.{property_path}\") LIKE \"{method_args[0]}%\""

        return f"{property_path} LIKE \"{method_args[0]}%\""
    
    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path in self.known_fields_mapping:
            property_redirect = self.known_fields_mapping[property_path]
            field = property_redirect.get("field")
            return f"{field} LIKE \"%{method_args[0]}\""

        if "*" in self.known_fields_mapping:
            json_redirect = self.known_fields_mapping["*"]
            field = json_redirect.get("field")        
            return f"json_extract({field}, \"$.{property_path}\") LIKE \"%{method_args[0]}\""

        return f"{property_path} LIKE \"%{method_args[0]}\""
