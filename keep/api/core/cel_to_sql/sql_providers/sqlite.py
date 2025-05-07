from datetime import datetime
from typing import List
from uuid import UUID

from keep.api.core.cel_to_sql.ast_nodes import ConstantNode, DataType
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToSqliteProvider(BaseCelToSqlProvider):

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        property_path_str = ".".join([f'"{item}"' for item in path])
        return f"json_extract({column}, '$.{property_path_str}')"

    def cast(self, expression_to_cast: str, to_type: DataType, force=False):
        if to_type == DataType.STRING:
            to_type_str = "TEXT"
        elif to_type == DataType.NULL:
            return expression_to_cast
        elif to_type == DataType.INTEGER or to_type == DataType.FLOAT:
            to_type_str = "REAL"
        elif to_type == DataType.DATETIME:
            return expression_to_cast
        elif to_type == DataType.BOOLEAN:
            cast_conditions = {
                # f"{expression_to_cast} is NULL": "FALSE",
                f"{expression_to_cast} = 'true'": "TRUE",
                f"{expression_to_cast} = 'false'": "FALSE",
                f"{expression_to_cast} = ''": "FALSE",
                f"CAST({expression_to_cast} AS SIGNED) >= 1": "TRUE",
                f"CAST({expression_to_cast} AS SIGNED) <= 0": "FALSE",
            }
            result = " ".join(
                [f"WHEN {key} THEN {value}" for key, value in cast_conditions.items()]
            )
            result = f"CASE {result} ELSE NULL END"
            return result
        else:
            raise ValueError(f"Unsupported type: {type}")

        return f"CAST({expression_to_cast} as {to_type_str})"

    def _visit_constant_node(
        self, value: str, expected_data_type: DataType = None
    ) -> str:
        if expected_data_type == DataType.UUID:
            str_value = str(value)
            try:
                # Because SQLite works with UUID without dashes, we need to convert it to a hex string
                # Example: 123e4567-e89b-12d3-a456-426614174000 -> 123e4567e89b12d3a456426614174000
                # Example2: 123e4567e89b12d3a456426614174000 -> 123e4567e89b12d3a456426614174000 (hex in CEL is also supported)
                value = UUID(str_value).hex
            except ValueError:
                pass

        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            date_exp = f"datetime({date_str})"
            return date_exp

        return super()._visit_constant_node(value, expected_data_type)

    def _visit_property_path(self, property_path: str) -> str:
        pass

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
