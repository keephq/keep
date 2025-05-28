from datetime import datetime
from typing import List
from uuid import UUID

from keep.api.core.cel_to_sql.ast_nodes import (
    ConstantNode,
    DataType,
    Node,
    PropertyAccessNode,
)
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToSqliteProvider(BaseCelToSqlProvider):

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        property_path_str = ".".join([f'"{item}"' for item in path])
        return f"json_extract({column}, '$.{property_path_str}')"

    def _json_contains_path(self, column: str, path: list[str]) -> str:
        """
        Generates a SQL expression to check if a JSON column contains a specific path.

        This method constructs a SQL query using SQLite's JSON functions to determine
        whether a JSON object in a specified column contains a given path. The path is
        represented as a list of keys, and the method supports both single-level and
        nested paths.

        Args:
            column (str): The name of the JSON column in the database table.
            path (list[str]): A list of keys representing the JSON path to check.

        Returns:
            str: A SQL expression that evaluates to true if the specified path exists
                 in the JSON column.

        Example:
            For a JSON column `json_column` and a path `['a', 'b', 'c']`, the method
            generates a SQL query similar to:
            ```
            EXISTS (
                SELECT 1
                FROM json_each(json_extract(json_column, '$.a.b'))
                WHERE json_each.key = 'c'
            )
            ```
        """
        json_each_exp = None
        key_name = None
        if len(path) == 1:
            json_each_exp = f"json_each({column})"
            key_name = path[0]
        else:
            last_key = path[-1]
            other_keys = path[:-1]
            json_each_exp = (
                f"json_each({self.json_extract_as_text(column, other_keys)})"
            )
            key_name = last_key

        return (
            f"EXISTS (SELECT 1 FROM {json_each_exp} WHERE json_each.key = '{key_name}')"
        )

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
                f"LOWER({expression_to_cast}) = 'true'": "TRUE",
                f"LOWER({expression_to_cast}) = 'false'": "FALSE",
                f"CAST({expression_to_cast} AS SIGNED) >= 1": "TRUE",
                f"{expression_to_cast} != ''": "TRUE",
            }
            result = " ".join(
                [f"WHEN {key} THEN {value}" for key, value in cast_conditions.items()]
            )
            result = f"CASE {result} ELSE FALSE END"
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

    def _visit_equal_for_array_datatype(
        self, first_operand: Node, second_operand: Node
    ) -> str:
        if not isinstance(first_operand, PropertyAccessNode):
            raise NotImplementedError(
                f"Array datatype comparison is not supported for {type(first_operand).__name__} node"
            )

        if not isinstance(second_operand, ConstantNode):
            raise NotImplementedError(
                f"Array datatype comparison is not supported for {type(second_operand).__name__} node"
            )
        prop = self._visit_property_access_node(first_operand, [])

        if second_operand.value is None:
            return f"({prop} IS NULL OR {prop} = '[]')"

        value = self._visit_constant_node(second_operand.value)[1:-1]

        return f"(SELECT 1 FROM json_each({prop}) as json_array WHERE json_array.value = '{value}')"

    def _visit_in_for_array_datatype(
        self, first_operand: Node, array: list[ConstantNode], stack: list[Node]
    ) -> str:
        in_opratation = self._visit_in(
            PropertyAccessNode(path=["json_array", "value"]), array, stack
        )
        column = self._visit_property_access_node(first_operand, [])
        array_filter = (
            f"(SELECT 1 FROM json_each({column}) as json_array WHERE {in_opratation})"
        )
        is_none_in_list = next((True for item in array if item.value is None), False)

        if is_none_in_list:
            return f"({column} = '[]' OR {column} IS NULL OR {array_filter})"

        return array_filter
