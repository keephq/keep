from datetime import datetime
from types import NoneType
from typing import List
from keep.api.core.cel_to_sql.ast_nodes import ConstantNode
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToSqliteProvider(BaseCelToSqlProvider):
    def json_extract_as_text(self, column: str, path: str) -> str:
        return f"json_extract({column}, '$.{path}')"

    def coalesce(self, args):
        coalesce_args = args

        if len(args) == 1:
            coalesce_args += ["NULL"]

        return f"COALESCE({', '.join(coalesce_args)})"

    def cast(self, expression_to_cast: str, to_type):
        if to_type is str:
            to_type_str = "TEXT"
        elif to_type is NoneType:
            return expression_to_cast
        elif to_type is int or to_type is float:
            to_type_str = "REAL"
        elif to_type is datetime:
            return expression_to_cast
        else:
            raise ValueError(f"Unsupported type: {type}")

        return f"CAST({expression_to_cast} as {to_type_str})"

    def _visit_constant_node(self, value: str) -> str:
        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            date_exp = f"datetime({date_str})"
            return date_exp

        return super()._visit_constant_node(value)

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.contains accepts 1 argument but got {len(method_args)}')

        processed_literal = self.literal_proc(f"*{method_args[0].value}*")
        return (
            f"{property_path} IS NOT NULL AND {property_path} GLOB {processed_literal}"
        )

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.startsWith accepts 1 argument but got {len(method_args)}')
        processed_literal = self.literal_proc(f"{method_args[0].value}*")
        return (
            f"{property_path} IS NOT NULL AND {property_path} GLOB {processed_literal}"
        )

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        if len(method_args) != 1:
            raise ValueError(f'{property_path}.endsWith accepts 1 argument but got {len(method_args)}')

        processed_literal = self.literal_proc(f"*{method_args[0].value}")
        return (
            f"{property_path} IS NOT NULL AND {property_path} GLOB {processed_literal}"
        )
