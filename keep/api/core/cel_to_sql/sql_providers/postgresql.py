from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    LogicalNode,
    LogicalNodeOperator,
    Node,
    PropertyAccessNode,
    DataType,
)
from keep.api.core.cel_to_sql.properties_metadata import JsonFieldMapping, SimpleFieldMapping
from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider


class CelToPostgreSqlProvider(BaseCelToSqlProvider):
    # -------------------------
    # JSON helpers
    # -------------------------

    @staticmethod
    def _escape_jsonpath_key(key: str) -> str:
        # JSONPath quoted member: $"a"."b"
        # Escape embedded double quotes.
        return key.replace('"', '\\"')

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        # (json_column -> 'labels' -> 'tags') ->> 'service'
        # Use literal quoting for each path piece as text.
        all_columns = [column] + [self.literal_proc(str(item)) for item in path]
        json_property_path = " -> ".join(all_columns[:-1])
        return f"({json_property_path}) ->> {all_columns[-1]}"

    def _json_contains_path(self, column: str, path: list[str]) -> str:
        if not path:
            # Root always "exists" if JSON is not null.
            return f"({column} IS NOT NULL)"
        property_path_str = ".".join([f'"{self._escape_jsonpath_key(item)}"' for item in path])
        return f"JSONB_PATH_EXISTS({column}::JSONB, '$.{property_path_str}')"

    # -------------------------
    # Casting
    # -------------------------

    def cast(self, expression_to_cast: str, to_type: DataType, force: bool = False) -> str:
        if to_type == DataType.NULL:
            return expression_to_cast

        if to_type == DataType.STRING:
            return f"({expression_to_cast})::TEXT"

        if to_type == DataType.INTEGER:
            # Choose INTEGER; if you actually need BIGINT, standardize it in DataType or metadata.
            return f"({expression_to_cast})::INTEGER"

        if to_type == DataType.FLOAT:
            return f"({expression_to_cast})::FLOAT"

        if to_type == DataType.DATETIME:
            return f"({expression_to_cast})::TIMESTAMP"

        if to_type == DataType.BOOLEAN:
            # Make behavior stable by operating on text.
            # Policy:
            # - "true"/"false" respected
            # - numeric strings: >=1 true else false
            # - non-empty string true
            expr_text = f"({expression_to_cast})::text"
            lower = f"LOWER({expr_text})"
            return (
                "CASE "
                f"WHEN {expression_to_cast} IS NULL THEN false "
                f"WHEN {lower} = 'true' THEN true "
                f"WHEN {lower} = 'false' THEN false "
                f"WHEN {expr_text} ~ '^[-+]?[0-9]*\\.?[0-9]+$' THEN (CAST({expr_text} AS FLOAT) >= 1) "
                f"WHEN {lower} <> '' THEN true "
                "ELSE false END"
            )

        raise ValueError(f"Unsupported type: {to_type}")

    def get_field_expression(self, cel_field: str) -> str:
        """
        PostgreSQL override:
        JSON ops return text; cast JSON extracted values to metadata type for correct ordering/comparison.
        """
        metadata = self.properties_metadata.get_property_metadata_for_str(cel_field)
        field_expressions: list[str] = []

        for field_mapping in metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                json_exp = self.json_extract_as_text(field_mapping.json_prop, field_mapping.prop_in_json)
                if metadata.data_type and metadata.data_type != DataType.STRING:
                    json_exp = self.cast(json_exp, metadata.data_type)
                field_expressions.append(json_exp)
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
            str_value = str(value)
            try:
                value = str(UUID(str_value))
            except ValueError:
                pass

        if isinstance(value, datetime):
            date_str = self.literal_proc(value.strftime("%Y-%m-%d %H:%M:%S"))
            return f"CAST({date_str} AS TIMESTAMP)"

        return super()._visit_constant_node(value, expected_data_type)

    # -------------------------
    # ILIKE builders (safe + predictable)
    # -------------------------

    @staticmethod
    def _escape_like_literal(raw: str) -> str:
        # Escape LIKE metacharacters. We'll use ESCAPE '\'
        return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _ilike(self, property_path: str, raw_value: str, mode: str) -> str:
        v = str(raw_value)
        v = self._escape_like_literal(v)
        lit = self.literal_proc(v)  # quoted + escaped for SQL

        if mode == "contains":
            pattern = f"('%' || {lit} || '%')"
        elif mode == "starts":
            pattern = f"({lit} || '%')"
        elif mode == "ends":
            pattern = f"('%' || {lit})"
        else:
            raise ValueError(f"Unknown ILIKE mode: {mode}")

        return f"{property_path} IS NOT NULL AND {property_path} ILIKE {pattern} ESCAPE '\\\\'"

    def _visit_contains_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.contains accepts 1 argument but got {len(method_args)}")
        return self._ilike(property_path, method_args[0].value, mode="contains")

    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.startsWith accepts 1 argument but got {len(method_args)}")
        return self._ilike(property_path, method_args[0].value, mode="starts")

    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        if len(method_args) != 1:
            raise ValueError(f"{property_path}.endsWith accepts 1 argument but got {len(method_args)}")
        return self._ilike(property_path, method_args[0].value, mode="ends")

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
            return f"({prop}::jsonb @> '[null]' OR {prop} IS NULL OR jsonb_array_length({prop}::jsonb) = 0)"

        if constant_node_value.startswith("'") and constant_node_value.endswith("'"):
            constant_node_value = constant_node_value[1:-1]

        # Escape double-quotes inside JSON string value
        constant_node_value = constant_node_value.replace('"', '\\"')
        return f"{prop}::jsonb @> '[\"{constant_node_value}\"]'"

    def _visit_in_for_array_datatype(self, first_operand: Node, array: list[ConstantNode], stack: list[Node]) -> str:
        if not array:
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