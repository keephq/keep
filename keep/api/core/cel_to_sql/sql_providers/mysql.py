from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    DataType,
    LogicalNode,
    LogicalNodeOperator,
    Node,
    PropertyAccessNode,
)
from keep.api.core.cel_to_sql.properties_metadata import JsonFieldMapping, SimpleFieldMapping
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToMySqlProvider(BaseCelToSqlProvider):
    # -------------------------
    # JSON helpers
    # -------------------------

    @staticmethod
    def _escape_json_path_key(key: str) -> str:
        """
        MySQL JSON path supports quoted members: $."a"."b"
        Escape embedded double quotes to avoid invalid SQL.
        """
        return key.replace('"', '\\"')

    def _json_path(self, path: list[str]) -> str:
        # $."a"."b"
        parts = [f'"{self._escape_json_path_key(p)}"' for p in path]
        return "$." + ".".join(parts)

    def _json_extract(self, column: str, path: list[str]) -> str:
        return f"JSON_EXTRACT({column}, '{self._json_path(path)}')"

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        # Unquote -> text
        return f"JSON_UNQUOTE({self._json_extract(column, path)})"

    def _json_contains_path(self, column: str, path: list[str]) -> str:
        return f"JSON_CONTAINS_PATH({column}, 'one', '{self._json_path(path)}')"

    # -------------------------
    # Casting
    # -------------------------

    def cast(self, expression_to_cast: str, to_type: DataType, force: bool = False) -> str:
        if to_type == DataType.BOOLEAN:
            # MySQL is… “creative” with truthiness. We force a stable mapping.
            expr = expression_to_cast
            numeric = f"CAST({expr} AS SIGNED)"

            # Ordered CASE matters.
            return (
                "CASE "
                f"WHEN {expr} IS NULL THEN FALSE "
                f"WHEN LOWER({expr}) = 'true' THEN TRUE "
                f"WHEN LOWER({expr}) = 'false' THEN FALSE "
                f"WHEN {numeric} >= 1 THEN TRUE "
                f"WHEN {numeric} = 0 THEN FALSE "
                f"WHEN {expr} != '' THEN TRUE "
                "ELSE FALSE END"
            )

        # MySQL generally casts implicitly; only force when asked.
        if not force:
            return expression_to_cast

        if to_type == DataType.INTEGER:
            return f"CAST({expression_to_cast} AS SIGNED)"
        if to_type == DataType.FLOAT:
            return f"CAST({expression_to_cast} AS DOUBLE)"

        return expression_to_cast

    # -------------------------
    # ORDER BY
    # -------------------------

    def get_order_by_expression(self, sort_options: list[tuple[str, str]]) -> str:
        sort_expressions: list[str] = []
        for sort_by, sort_dir in sort_options:
            direction = "ASC" if (sort_dir or "").lower() == "asc" else "DESC"
            order_by_exp = self._get_order_by_field(sort_by)
            sort_expressions.append(f"{order_by_exp} {direction}")
        return ", ".join(sort_expressions)

    def _get_order_by_field(self, cel_sort_by: str) -> str:
        """
        Overridden: For MySQL sorting we want JSON_EXTRACT without JSON_UNQUOTE
        so numeric/date ordering behaves as MySQL expects.
        """
        metadata = self.properties_metadata.get_property_metadata_for_str(cel_sort_by)
        field_expressions: list[str] = []

        for field_mapping in metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                field_expressions.append(self._json_extract(field_mapping.json_prop, field_mapping.prop_in_json))
                continue
            if isinstance(field_mapping, SimpleFieldMapping):
                field_expressions.append(field_mapping.map_to)
                continue
            raise ValueError(f"Unsupported field mapping type: {type(field_mapping)}")

        return self.coalesce(field_expressions) if len(field_expressions) > 1 else field_expressions[0]

    # -------------------------
    # Constants
    # -------------------------

    def _visit_constant_node(self, value, expected_data_type: DataType = None) -> str:
        if expected_data_type == DataType.UUID:
            # MySQL UUID often stored without dashes.
            str_value = str(value)
            try:
                value = UUID(str_value).hex
            except ValueError:
                # If it isn't a UUID, let the base logic handle it (it will be quoted).
                pass

        if isinstance(value, datetime):
            # Keep it explicit and stable.
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            return f"CAST({date_str} AS DATETIME)"

        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        return super()._visit_constant_node(value, expected_data_type)

    # -------------------------
    # LIKE builders (safe + predictable)
    # -------------------------

    @staticmethod
    def _escape_like_literal(raw: str) -> str:
        """
        Escape LIKE wildcards so user input doesn't become pattern syntax.
        """
        return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _like(self, property_path: str, raw_value: str, mode: str) -> str:
        """
        mode: 'contains' | 'starts' | 'ends'
        """
        v = raw_value.lower()
        v = self._escape_like_literal(v)

        lit = self.literal_proc(v)  # quoted string, safely escaped for dialect
        if mode == "contains":
            pattern = f"CONCAT('%', {lit}, '%')"
        elif mode == "starts":
            pattern = f"CONCAT({lit}, '%')"
        elif mode == "ends":
            pattern = f"CONCAT('%', {lit})"
        else:
            raise ValueError(f"Unknown LIKE mode: {mode}")

        # ESCAPE '\\' makes our backslash escapes meaningful.
        return f"{property_path} IS NOT NULL AND LOWER({property_path}) LIKE {pattern} ESCAPE '\\\\'"

    def _visit_contains_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.contains accepts 1 argument but got {len(method_args)}")
        arg = method_args[0].value
        if not isinstance(arg, str):
            arg = str(arg)
        return self._like(property_path, arg, mode="contains")

    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.startsWith accepts 1 argument but got {len(method_args)}")
        arg = method_args[0].value
        if not isinstance(arg, str):
            arg = str(arg)
        return self._like(property_path, arg, mode="starts")

    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.endsWith accepts 1 argument but got {len(method_args)}")
        arg = method_args[0].value
        if not isinstance(arg, str):
            arg = str(arg)
        return self._like(property_path, arg, mode="ends")

    # -------------------------
    # Array datatype operators
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
        constant_node_value = self._visit_constant_node(second_operand.value)

        if constant_node_value == "NULL":
            return f"(JSON_CONTAINS({prop}, '[null]') OR {prop} IS NULL OR JSON_LENGTH({prop}) = 0)"

        # If quoted, unquote safely (we only use it inside a JSON string literal)
        if constant_node_value.startswith("'") and constant_node_value.endswith("'"):
            constant_node_value = constant_node_value[1:-1]

        # Escape double-quotes inside JSON string content
        constant_node_value = constant_node_value.replace('"', '\\"')
        return f"JSON_CONTAINS({prop}, '[\"{constant_node_value}\"]')"

    def _visit_in_for_array_datatype(self, first_operand: Node, array: list[ConstantNode], stack: list[Node]) -> str:
        if not array:
            # Empty IN => always false
            return self._visit_constant_node(False)

        node: Node | None = None
        for item in array:
            current_node = ComparisonNode(
                first_operand=first_operand,
                operator=ComparisonNodeOperator.EQ,
                second_operand=item,
            )
            node = current_node if node is None else LogicalNode(
                left=node,
                operator=LogicalNodeOperator.OR,
                right=current_node,
            )

        return self._build_sql_filter(node, stack)