from __future__ import annotations

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
    # -------------------------
    # JSON helpers
    # -------------------------

    @staticmethod
    def _escape_jsonpath_key(key: str) -> str:
        # SQLite JSON path uses quoted keys like: $.\"a\".\"b\"
        # We build: $."a"."b" so we must escape embedded double quotes.
        return key.replace('"', '\\"')

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        if not path:
            # Root extraction; json_extract(col, '$') returns the JSON value
            return f"json_extract({column}, '$')"

        property_path_str = ".".join([f'"{self._escape_jsonpath_key(item)}"' for item in path])
        return f"json_extract({column}, '$.{property_path_str}')"

    def _json_contains_path(self, column: str, path: list[str]) -> str:
        """
        Check if a JSON object contains a given key at a path.
        Uses json_each() to inspect object members.
        """
        if not path:
            return f"({column} IS NOT NULL)"

        if len(path) == 1:
            json_each_exp = f"json_each({column})"
            key_name = path[0]
        else:
            last_key = path[-1]
            other_keys = path[:-1]
            json_each_exp = f"json_each({self.json_extract_as_text(column, other_keys)})"
            key_name = last_key

        # IMPORTANT: key_name must be literal-escaped, not interpolated.
        key_lit = self.literal_proc(str(key_name))
        return f"EXISTS (SELECT 1 FROM {json_each_exp} WHERE json_each.key = {key_lit})"

    # -------------------------
    # Casting
    # -------------------------

    def cast(self, expression_to_cast: str, to_type: DataType, force: bool = False) -> str:
        if to_type == DataType.NULL:
            return expression_to_cast

        if to_type == DataType.STRING:
            return f"CAST({expression_to_cast} AS TEXT)"

        if to_type == DataType.INTEGER:
            return f"CAST({expression_to_cast} AS INTEGER)"

        if to_type == DataType.FLOAT:
            return f"CAST({expression_to_cast} AS REAL)"

        if to_type == DataType.DATETIME:
            # SQLite stores datetimes as TEXT/REAL/INTEGER. Provider chooses to leave it as-is.
            # If you want strict behavior, normalize to datetime(...) here.
            return expression_to_cast

        if to_type == DataType.BOOLEAN:
            # Normalize via TEXT checks + numeric check.
            # NOTE: We cast to TEXT for LOWER() to avoid type weirdness.
            expr_text = f"CAST({expression_to_cast} AS TEXT)"
            lower = f"LOWER({expr_text})"
            return (
                "CASE "
                f"WHEN {expression_to_cast} IS NULL THEN 0 "
                f"WHEN {lower} = 'true' THEN 1 "
                f"WHEN {lower} = 'false' THEN 0 "
                f"WHEN {expr_text} GLOB '-*[0-9]*.*[0-9]*' OR {expr_text} GLOB '[0-9]*.*[0-9]*' "
                f"THEN (CAST({expression_to_cast} AS REAL) >= 1) "
                f"WHEN {lower} <> '' THEN 1 "
                "ELSE 0 END"
            )

        raise ValueError(f"Unsupported type: {to_type}")

    # -------------------------
    # Constants
    # -------------------------

    def _visit_constant_node(self, value, expected_data_type: DataType = None) -> str:
        if expected_data_type == DataType.UUID:
            str_value = str(value)
            try:
                value = UUID(str_value).hex
            except ValueError:
                pass

        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            return f"datetime({date_str})"

        return super()._visit_constant_node(value, expected_data_type)

    # -------------------------
    # LIKE builders (safe + predictable)
    # -------------------------

    @staticmethod
    def _escape_like_literal(raw: str) -> str:
        # Escape LIKE wildcards for SQLite; we use ESCAPE '\'
        return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _like(self, property_path: str, raw_value: str, mode: str) -> str:
        v = self._escape_like_literal(str(raw_value))
        lit = self.literal_proc(v)  # quoted safely

        if mode == "contains":
            pattern = f"('%' || {lit} || '%')"
        elif mode == "starts":
            pattern = f"({lit} || '%')"
        elif mode == "ends":
            pattern = f"('%' || {lit})"
        else:
            raise ValueError(f"Unknown LIKE mode: {mode}")

        return f"{property_path} IS NOT NULL AND {property_path} LIKE {pattern} ESCAPE '\\\\'"

    def _visit_contains_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.contains accepts 1 argument but got {len(method_args)}")
        return self._like(property_path, method_args[0].value, mode="contains")

    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.startsWith accepts 1 argument but got {len(method_args)}")
        return self._like(property_path, method_args[0].value, mode="starts")

    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.endsWith accepts 1 argument but got {len(method_args)}")
        return self._like(property_path, method_args[0].value, mode="ends")

    # -------------------------
    # Array datatype ops
    # -------------------------

    def _visit_equal_for_array_datatype(self, first_operand: Node, second_operand: Node) -> str:
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

        # Build safe constant literal for comparison
        lit = self._visit_constant_node(second_operand.value)

        # json_each.value is returned as text/number depending on JSON; compare as TEXT for stability
        return f"EXISTS (SELECT 1 FROM json_each({prop}) AS json_array WHERE CAST(json_array.value AS TEXT) = CAST({lit} AS TEXT))"

    def _visit_in_for_array_datatype(self, first_operand: Node, array: list[ConstantNode], stack: list[Node]) -> str:
        if not array:
            return self._visit_constant_node(False)

        # Build IN operation against json_each alias
        in_operation = self._visit_in(
            PropertyAccessNode(path=["json_array", "value"]), array, stack
        )
        column = self._visit_property_access_node(first_operand, [])
        array_filter = f"EXISTS (SELECT 1 FROM json_each({column}) AS json_array WHERE {in_operation})"

        is_none_in_list = any(item.value is None for item in array)
        if is_none_in_list:
            return f"({column} = '[]' OR {column} IS NULL OR {array_filter})"

        return array_filter