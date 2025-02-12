from datetime import datetime
from types import NoneType
from typing import List
from keep.api.core.cel_to_sql.ast_nodes import ConstantNode
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider

class CelToMySqlProvider(BaseCelToSqlProvider):
    def json_extract_as_text(self, column: str, path: str) -> str:
        return f"JSON_UNQUOTE(JSON_EXTRACT({column}, '$.{path}'))"

    def cast(self, expression_to_cast, to_type):
        # MySQL does not need explicit cast because it does it implicitly
        return expression_to_cast

    def _visit_constant_node(self, value: str) -> str:
        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            date_exp = f"CAST({date_str} as DATETIME)"
            return date_exp

        return super()._visit_constant_node(value)

    def coalesce(self, args):
        return f"COALESCE({', '.join(args)})"

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.contains accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} LIKE '%{unquoted_literal}%'"

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.startsWith accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} LIKE '{unquoted_literal}%'"

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.endsWith accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(method_args[0].value)
        unquoted_literal = processed_literal[1:-1]
        return f"{property_path} IS NOT NULL AND {property_path} LIKE '%{unquoted_literal}'"
