from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToMySqlProvider(BaseCelToSqlProvider):
    def _json_merge(self, columns: List[str]) -> str:
        return f"json_patch({', '.join(columns)})"

    def json_extract(self, column: str, path: str) -> str:
        return f"JSON_UNQUOTE(JSON_EXTRACT({column}, \"$.{path}\"))"
    
    def coalesce(self, args):
        return f"COALESCE({', '.join(args)})"
    
    def _visit_contains_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"%{method_args[0]}%\""
    
    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"{method_args[0]}%\""
    
    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[str]) -> str:
        return f"{property_path} LIKE \"%{method_args[0]}\""
