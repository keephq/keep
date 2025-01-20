from types import NoneType
from typing import List
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToPostgreSqlProvider(BaseCelToSqlProvider):
    def json_extract(self, column: str, path: str) -> str:
        return " -> ".join(
            [column] + [f"'{item}'" for item in path.split(".")]
        )  # example: 'json_column' -> 'key1' -> 'key2'

    def json_extract_as_text(self, column: str, path: str) -> str:
        return " ->> ".join([column] + [f"'{item}'" for item in path.split(".")])

    def coalesce(self, args):
        coalesce_args = args

        if len(args) == 1:
            coalesce_args += ["NULL"]

        return f"COALESCE({', '.join(args)})"

    def cast(self, exp, to_type):
        if to_type is str:
            to_type_str = "TEXT"
        elif to_type is int:
            to_type_str = "INTEGER"
        elif to_type is NoneType:
            return exp
        else:
            raise ValueError(f"Unsupported type: {type}")

        return f"{exp}::{to_type_str}"

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f'{property_path} LIKE "%{method_args[0]}%"'

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f'{property_path} LIKE "{method_args[0]}%"'

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        return f'{property_path} LIKE "%{method_args[0]}"'
