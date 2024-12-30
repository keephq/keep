from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToPostgreSqlProvider(BaseCelToSqlProvider):
    def _visit_property(self, property_path: str):
        if property_path.startswith('event'):
            property_access = property_path.replace('event.', '')
            return f"event ->> '{property_access}'"
        
        return super()._visit_property(property_path)
    
    def _visit_contains_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path and property_path.startswith('event'):
            prop = property_path.replace('event.', '')
            return f"event ->> '{prop}' LIKE '%{method_args[0]}%'"
        
        return f"{property_path} LIKE '%{method_args[0]}%'"
    
    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path and property_path.startswith('event'):
            prop = property_path.replace('event.', '')
            return f"event ->> '{prop}' LIKE '{method_args[0]}%'"
        
        return f"{property_path} LIKE '{method_args[0]}%'"
    
    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        if property_path and property_path.startswith('event'):
            prop = property_path.replace('event.', '')
            return f"event ->> '{prop}' LIKE '%{method_args[0]}'"
        
        return f"{property_path} LIKE '%{method_args[0]}'"