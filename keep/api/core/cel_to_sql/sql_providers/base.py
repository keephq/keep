from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence

from sqlalchemy import Dialect, Boolean, Integer, Float, String
from celpy import CELParseError

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNodeOperator,
    ConstantNode,
    DataType,
    LogicalNodeOperator,
    MemberAccessNode,
    Node,
    LogicalNode,
    ComparisonNode,
    UnaryNode,
    PropertyAccessNode,
    ParenthesisNode,
    UnaryNodeOperator,
    from_type_to_data_type,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
from keep.api.core.cel_to_sql.properties_mapper import (
    JsonPropertyAccessNode,
    MultipleFieldsNode,
    PropertiesMapper,
    PropertiesMappingException,
)
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertiesMetadata,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)


class CelToSqlException(Exception):
    pass


@dataclass(frozen=True)
class CelToSqlResult:
    sql: str
    involved_fields: List[PropertyMetadataInfo]


class BaseCelToSqlProvider(ABC):
    """
    Converts CEL AST nodes into a SQL string.
    This is still "string SQL", but hardened: bounded recursion, safe stack handling,
    better validation, consistent NULL semantics, and enforced abstract hooks.
    """

    MAX_RECURSION_DEPTH = 100  # DoS protection

    def __init__(self, dialect: Dialect, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata
        self.properties_mapper = PropertiesMapper(properties_metadata)

        # Dialect-specific literal processors for common types.
        # These return SQL literals (quoted/escaped) appropriate for that dialect.
        self._lit_str = String().literal_processor(dialect=dialect)
        self._lit_bool = Boolean().literal_processor(dialect=dialect)
        self._lit_int = Integer().literal_processor(dialect=dialect)
        self._lit_float = Float().literal_processor(dialect=dialect)

    # ---------------------------
    # Public API
    # ---------------------------

    def convert_to_sql_str(self, cel: str) -> str:
        return self.convert_to_sql_str_v2(cel).sql

    def convert_to_sql_str_v2(self, cel: str) -> CelToSqlResult:
        if not cel:
            return CelToSqlResult(sql="", involved_fields=[])

        try:
            original_query = CelToAstConverter.convert_to_ast(cel)
        except CELParseError as e:
            raise CelToSqlException(f"Error parsing CEL expression: {e}") from e

        try:
            with_mapped_props, involved_fields = self.properties_mapper.map_props_in_ast(original_query)
        except PropertiesMappingException as e:
            raise CelToSqlException(f"Error while mapping columns: {e}") from e

        if not with_mapped_props:
            return CelToSqlResult(sql="", involved_fields=[])

        try:
            sql_filter = self._build_sql_filter(with_mapped_props, stack=[], original_cel=cel)
            return CelToSqlResult(sql=sql_filter, involved_fields=involved_fields)
        except NotImplementedError as e:
            raise CelToSqlException(f"Error while converting CEL expression tree to SQL: {e}") from e

    def get_order_by_expression(self, sort_options: list[tuple[str, str]]) -> str:
        sort_expressions: list[str] = []
        for sort_by, sort_dir in sort_options:
            sort_dir_norm = (sort_dir or "").lower()
            order_by_exp = self.get_field_expression(sort_by)
            sort_expressions.append(f"{order_by_exp} {'ASC' if sort_dir_norm == 'asc' else 'DESC'}")
        return ", ".join(sort_expressions)

    def get_field_expression(self, cel_field: str) -> str:
        metadata = self.properties_metadata.get_property_metadata_for_str(cel_field)
        field_expressions: list[str] = []

        for field_mapping in metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                field_expressions.append(
                    self.json_extract_as_text(field_mapping.json_prop, field_mapping.prop_in_json)
                )
            elif isinstance(field_mapping, SimpleFieldMapping):
                field_expressions.append(field_mapping.map_to)
            else:
                raise ValueError(f"Unsupported field mapping type: {type(field_mapping)}")

        return self.coalesce(field_expressions) if len(field_expressions) > 1 else field_expressions[0]

    # ---------------------------
    # Abstract hooks that MUST be provided per dialect
    # ---------------------------

    @abstractmethod
    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        """Return SQL that extracts JSON value as text for this dialect."""
        raise NotImplementedError

    @abstractmethod
    def _json_contains_path(self, column: str, path: list[str]) -> str:
        """Return SQL that checks JSON has a path for this dialect."""
        raise NotImplementedError

    @abstractmethod
    def cast(self, expression_to_cast: str, to_type: DataType, force: bool = False) -> str:
        """Return SQL CAST for this dialect."""
        raise NotImplementedError

    @abstractmethod
    def _visit_equal_for_array_datatype(self, first_operand: Node, second_operand: Node) -> str:
        raise NotImplementedError

    @abstractmethod
    def _visit_in_for_array_datatype(self, first_operand: Node, array: list[ConstantNode], stack: list[Node]) -> str:
        raise NotImplementedError

    @abstractmethod
    def _visit_contains_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        raise NotImplementedError

    @abstractmethod
    def _visit_starts_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        raise NotImplementedError

    @abstractmethod
    def _visit_ends_with_method_calling(self, property_path: str, method_args: List[ConstantNode]) -> str:
        raise NotImplementedError

    # ---------------------------
    # Core helpers
    # ---------------------------

    def coalesce(self, args: Sequence[str]) -> str:
        if len(args) == 1:
            return args[0]
        return f"COALESCE({', '.join(args)})"

    def literal_proc(self, value: Any) -> str:
        """
        Convert Python primitive into a dialect-safe SQL literal.
        Anything exotic must be implemented intentionally, not via str().
        """
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            # Some dialects return 'true'/'false', others 1/0, etc.
            return self._lit_bool(value) if self._lit_bool else ("true" if value else "false")
        if isinstance(value, int) and not isinstance(value, bool):
            return self._lit_int(value) if self._lit_int else str(value)
        if isinstance(value, float):
            return self._lit_float(value) if self._lit_float else str(value)
        if isinstance(value, str):
            return self._lit_str(value) if self._lit_str else f"'{value.replace(\"'\", \"''\")}'"

        raise CelToSqlException(f"Unsupported literal type: {type(value).__name__}")

    def _build_sql_filter(self, abstract_node: Node, stack: list[Node], original_cel: str) -> str:
        if len(stack) >= self.MAX_RECURSION_DEPTH:
            raise CelToSqlException(
                f"CEL expression too deeply nested (max depth: {self.MAX_RECURSION_DEPTH})"
            )

        stack.append(abstract_node)
        try:
            if isinstance(abstract_node, ParenthesisNode):
                return self._visit_parentheses(self._build_sql_filter(abstract_node.expression, stack, original_cel))

            elif isinstance(abstract_node, LogicalNode):
                return self._visit_logical_node(abstract_node, stack, original_cel)

            elif isinstance(abstract_node, ComparisonNode):
                return self._visit_comparison_node(abstract_node, stack, original_cel)

            elif isinstance(abstract_node, MemberAccessNode):
                return self._visit_member_access_node(abstract_node, stack, original_cel)

            elif isinstance(abstract_node, UnaryNode):
                return self._visit_unary_node(abstract_node, stack, original_cel)

            elif isinstance(abstract_node, ConstantNode):
                return self._visit_constant_node(abstract_node.value)

            elif isinstance(abstract_node, MultipleFieldsNode):
                return self._visit_multiple_fields_node(abstract_node, cast_to=None, stack=stack, original_cel=original_cel)

            raise NotImplementedError(
                f"{type(abstract_node).__name__} node type is not supported yet "
                f"(stack depth: {len(stack)})."
            )
        finally:
            stack.pop()

    def _visit_parentheses(self, node_sql: str) -> str:
        return f"({node_sql})"

    # ---------------------------
    # Logical visitors
    # ---------------------------

    def _visit_logical_node(self, logical_node: LogicalNode, stack: list[Node], original_cel: str) -> str:
        left = self._build_sql_filter(logical_node.left, stack, original_cel)
        right = self._build_sql_filter(logical_node.right, stack, original_cel)

        if logical_node.operator == LogicalNodeOperator.AND:
            return f"({left} AND {right})"
        if logical_node.operator == LogicalNodeOperator.OR:
            return f"({left} OR {right})"

        raise NotImplementedError(f"{logical_node.operator} logical operator is not supported yet")

    # ---------------------------
    # Comparison visitors
    # ---------------------------

    def _visit_comparison_node(self, comparison_node: ComparisonNode, stack: list[Node], original_cel: str) -> str:
        op = comparison_node.operator

        # Special-case IN early
        if op == ComparisonNodeOperator.IN:
            second_list = (
                comparison_node.second_operand
                if isinstance(comparison_node.second_operand, list)
                else [comparison_node.second_operand]
            )
            if not all(isinstance(x, ConstantNode) for x in second_list):
                raise CelToSqlException("IN operator requires an array of constants")

            if (
                isinstance(comparison_node.first_operand, PropertyAccessNode)
                and comparison_node.first_operand.data_type == DataType.ARRAY
            ):
                return self._visit_in_for_array_datatype(comparison_node.first_operand, second_list, stack)

            return self._visit_in(comparison_node.first_operand, second_list, stack, original_cel)

        # Array EQ special-case
        if (
            op == ComparisonNodeOperator.EQ
            and isinstance(comparison_node.first_operand, PropertyAccessNode)
            and comparison_node.first_operand.data_type == DataType.ARRAY
        ):
            return self._visit_equal_for_array_datatype(comparison_node.first_operand, comparison_node.second_operand)

        first_operand_sql = self._build_sql_filter(comparison_node.first_operand, stack, original_cel)
        second_operand_sql = self._build_sql_filter(comparison_node.second_operand, stack, original_cel)

        # Determine casting behavior
        force_cast = isinstance(comparison_node.first_operand, JsonPropertyAccessNode)
        if isinstance(comparison_node.first_operand, MultipleFieldsNode):
            if not comparison_node.first_operand.fields:
                raise CelToSqlException("MultipleFieldsNode has no fields")
            force_cast = any(isinstance(f, JsonPropertyAccessNode) for f in comparison_node.first_operand.fields)

        # If the RHS is a constant, we can infer desired type and cast LHS accordingly
        rhs_type: Optional[DataType] = None
        if isinstance(comparison_node.second_operand, ConstantNode):
            rhs_type = from_type_to_data_type(type(comparison_node.second_operand.value))

        if force_cast and rhs_type:
            first_operand_sql = self.cast(first_operand_sql, rhs_type, force=True)

        # Operators
        if op == ComparisonNodeOperator.EQ:
            return self._visit_equal(first_operand_sql, comparison_node.second_operand)
        if op == ComparisonNodeOperator.NE:
            return self._visit_not_equal(first_operand_sql, comparison_node.second_operand)
        if op == ComparisonNodeOperator.GT:
            return f"{first_operand_sql} > {second_operand_sql}"
        if op == ComparisonNodeOperator.GE:
            return f"{first_operand_sql} >= {second_operand_sql}"
        if op == ComparisonNodeOperator.LT:
            return f"{first_operand_sql} < {second_operand_sql}"
        if op == ComparisonNodeOperator.LE:
            return f"{first_operand_sql} <= {second_operand_sql}"
        if op == ComparisonNodeOperator.CONTAINS:
            return self._visit_contains_method_calling(first_operand_sql, [comparison_node.second_operand])
        if op == ComparisonNodeOperator.STARTS_WITH:
            return self._visit_starts_with_method_calling(first_operand_sql, [comparison_node.second_operand])
        if op == ComparisonNodeOperator.ENDS_WITH:
            return self._visit_ends_with_method_calling(first_operand_sql, [comparison_node.second_operand])

        raise NotImplementedError(f"{op} comparison operator is not supported yet")

    def _visit_equal(self, first_operand_sql: str, rhs_node: Node) -> str:
        # Consistent NULL handling: if RHS constant is None -> IS NULL
        if isinstance(rhs_node, ConstantNode) and rhs_node.value is None:
            return f"{first_operand_sql} IS NULL"
        rhs_sql = self._node_to_sql_literal(rhs_node)
        return f"{first_operand_sql} = {rhs_sql}"

    def _visit_not_equal(self, first_operand_sql: str, rhs_node: Node) -> str:
        if isinstance(rhs_node, ConstantNode) and rhs_node.value is None:
            return f"{first_operand_sql} IS NOT NULL"
        rhs_sql = self._node_to_sql_literal(rhs_node)
        return f"{first_operand_sql} != {rhs_sql}"

    def _node_to_sql_literal(self, node: Node) -> str:
        if isinstance(node, ConstantNode):
            return self._visit_constant_node(node.value)
        # Fall back to SQL built from node (non-constant comparisons)
        return self._build_sql_filter(node, stack=[], original_cel="")

    def _visit_in(self, first_operand: Node, array: list[ConstantNode], stack: list[Node], original_cel: str) -> str:
        if not array:
            # Empty IN is always false
            return self._visit_constant_node(False)

        # Build LHS
        if isinstance(first_operand, (JsonPropertyAccessNode, PropertyAccessNode)):
            first_operand_sql = self._visit_property_access_node(first_operand)
        elif isinstance(first_operand, MultipleFieldsNode):
            first_operand_sql = self._visit_multiple_fields_node(first_operand, cast_to=None, stack=stack, original_cel=original_cel)
        else:
            first_operand_sql = self._build_sql_filter(first_operand, stack, original_cel)

        # Separate NULLs from non-NULLs
        non_null = [c for c in array if c.value is not None]
        has_null = any(c.value is None for c in array)

        or_parts: list[str] = []

        if non_null:
            # Optional: strict type mismatch could raise instead of silently casting.
            # Keeping behavior: if mixed types, cast to string.
            first_type = type(non_null[0].value)
            mixed = any(type(c.value) is not first_type for c in non_null)
            cast_to = DataType.STRING if mixed else None
            lhs = self.cast(first_operand_sql, cast_to) if cast_to else first_operand_sql

            values_sql = ", ".join(self._visit_constant_node(c.value) for c in non_null)
            or_parts.append(f"{lhs} IN ({values_sql})")

        if has_null:
            or_parts.append(f"{first_operand_sql} IS NULL")

        if not or_parts:
            return self._visit_constant_node(False)

        # OR-chain
        expr = or_parts[0]
        for part in or_parts[1:]:
            expr = f"({expr} OR {part})"
        return expr

    # ---------------------------
    # Constants & member access
    # ---------------------------

    def _visit_constant_node(self, value: Any) -> str:
        return self.literal_proc(value)

    def _visit_multiple_fields_node(self, multiple_fields_node: MultipleFieldsNode, cast_to: Optional[DataType], stack: list[Node], original_cel: str) -> str:
        if not multiple_fields_node.fields:
            raise CelToSqlException("MultipleFieldsNode has no fields")

        coalesce_args: list[str] = []
        for item in multiple_fields_node.fields:
            arg = self._visit_property_access_node(item)
            if isinstance(item, JsonPropertyAccessNode) and cast_to:
                arg = self.cast(arg, cast_to)
            coalesce_args.append(arg)

        return coalesce_args[0] if len(coalesce_args) == 1 else self.coalesce(coalesce_args)

    def _visit_member_access_node(self, member_access_node: MemberAccessNode, stack: list[Node], original_cel: str) -> str:
        if isinstance(member_access_node, PropertyAccessNode):
            return self._visit_property_access_node(member_access_node)
        raise NotImplementedError(f"{type(member_access_node).__name__} member access node is not supported yet")

    def _visit_property_access_node(self, property_access_node: PropertyAccessNode) -> str:
        if isinstance(property_access_node, JsonPropertyAccessNode):
            return self.json_extract_as_text(property_access_node.json_property_name, property_access_node.property_to_extract)

        # Basic identifier/path sanity to avoid CEL injecting raw SQL identifiers.
        # (Still relies on metadata mapping for real safety.)
        for part in property_access_node.path:
            if not isinstance(part, str) or not part.replace("_", "").isalnum():
                raise CelToSqlException(f"Invalid identifier in property path: {part!r}")

        return ".".join(property_access_node.path)

    # ---------------------------
    # Unary visitors
    # ---------------------------

    def _visit_unary_node(self, unary_node: UnaryNode, stack: list[Node], original_cel: str) -> str:
        if unary_node.operator == UnaryNodeOperator.NOT:
            return f"NOT ({self._build_sql_filter(unary_node.operand, stack, original_cel)})"
        if unary_node.operator == UnaryNodeOperator.HAS:
            return self._visit_unary_has(unary_node.operand, stack, original_cel)

        raise NotImplementedError(f"{unary_node.operator} unary operator is not supported yet")

    def _visit_unary_has(self, operand: Node, stack: list[Node], original_cel: str) -> str:
        if isinstance(operand, JsonPropertyAccessNode):
            return self._json_contains_path(operand.json_property_name, operand.property_to_extract)

        if isinstance(operand, PropertyAccessNode):
            return "TRUE" if self.properties_metadata.get_property_metadata(operand.path) else "FALSE"

        if isinstance(operand, MultipleFieldsNode):
            node = self.__convert_to_or([
                UnaryNode(operator=UnaryNodeOperator.HAS, operand=field)
                for field in operand.fields
            ])
            return self._build_sql_filter(node, stack, original_cel)

        return "FALSE"

    def __convert_to_or(self, expressions: Sequence[Node]) -> Node:
        if not expressions:
            raise CelToSqlException("Cannot create OR expression from empty list")
        if len(expressions) == 1:
            return expressions[0]

        node: Node = expressions[0]
        for expression in expressions[1:]:
            node = LogicalNode(left=node, operator=LogicalNodeOperator.OR, right=expression)
        return node