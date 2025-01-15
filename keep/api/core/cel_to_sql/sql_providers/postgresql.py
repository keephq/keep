from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToPostgreSqlProvider(BaseCelToSqlProvider):
    def json_extract(self, column: str, path: str) -> str:
        ' -> '.join([column] + path.split('.'))
        return ' -> '.join([column] + path.split('.')) # example: 'json_column' -> 'key1' -> 'key2'
    
    def coalesce(self, args):
        return f"COALESCE({', '.join(args)})"
    
    def _visit_contains_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"%{method_args[0]}%\""
    
    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"{method_args[0]}%\""
    
    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"%{method_args[0]}\""