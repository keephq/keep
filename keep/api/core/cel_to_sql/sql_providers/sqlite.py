from types import NoneType
from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToSqliteProvider(BaseCelToSqlProvider):
    def json_extract_as_text(self, column: str, path: str) -> str:
        return f"json_extract({column}, '$.{path}')"

    def coalesce(self, args):
        coalesce_args = args

        if len(args) == 1:
            coalesce_args += ["NULL"]

        return f"COALESCE({', '.join(coalesce_args)})"

    def cast(self, exp, to_type):
        if to_type is str:
            to_type_str = "TEXT"
        elif to_type is NoneType:
            return exp
        else:
            raise ValueError(f"Unsupported type: {type}")

        return f"CAST({exp} as {to_type_str})"

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f'{property_path} LIKE '%{method_args[0]}%''

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f"{property_path} LIKE '{method_args[0]}%'"

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f"{property_path} LIKE '%{method_args[0]}'"
