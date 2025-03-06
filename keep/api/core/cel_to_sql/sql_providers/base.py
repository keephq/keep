from typing import Any, List
from types import NoneType

from sqlalchemy import Dialect, String

from keep.api.core.cel_to_sql.ast_nodes import (
    ConstantNode,
    MemberAccessNode,
    Node,
    LogicalNode,
    ComparisonNode,
    UnaryNode,
    PropertyAccessNode,
    MethodAccessNode,
    ParenthesisNode,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter

from keep.api.core.cel_to_sql.properties_mapper import JsonPropertyAccessNode, MultipleFieldsNode, PropertiesMapper, PropertiesMappingException
from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata
from celpy import CELParseError


class CelToSqlException(Exception):
    pass

class BaseCelToSqlProvider:
    """
    Base class for converting CEL (Common Expression Language) expressions to SQL strings.
    Methods:
        convert_to_sql_str(cel: str) -> BuiltQueryMetadata:
            Converts a CEL expression to an SQL string.
        json_extract(column: str, path: str) -> str:
            Abstract method to extract JSON data from a column. Must be implemented in the child class.
        coalesce(args: List[str]) -> str:
            Abstract method to perform COALESCE operation. Must be implemented in the child class.
        _visit_parentheses(node: str) -> str:
            Wraps a given SQL string in parentheses.
        _visit_logical_node(logical_node: LogicalNode) -> str:
            Visits a logical node and converts it to an SQL string.
        _visit_logical_and(left: str, right: str) -> str:
            Converts a logical AND operation to an SQL string.
        _visit_logical_or(left: str, right: str) -> str:
            Converts a logical OR operation to an SQL string.
        _visit_comparison_node(comparison_node: ComparisonNode) -> str:
            Visits a comparison node and converts it to an SQL string.
        _visit_equal(first_operand: str, second_operand: str) -> str:
            Converts an equality comparison to an SQL string.
        _visit_not_equal(first_operand: str, second_operand: str) -> str:
            Converts a not-equal comparison to an SQL string.
        _visit_greater_than(first_operand: str, second_operand: str) -> str:
            Converts a greater-than comparison to an SQL string.
        _visit_greater_than_or_equal(first_operand: str, second_operand: str) -> str:
            Converts a greater-than-or-equal comparison to an SQL string.
        _visit_less_than(first_operand: str, second_operand: str) -> str:
            Converts a less-than comparison to an SQL string.
        _visit_less_than_or_equal(first_operand: str, second_operand: str) -> str:
            Converts a less-than-or-equal comparison to an SQL string.
        _visit_in(first_operand: Node, array: list[ConstantNode]) -> str:
            Converts an IN operation to an SQL string.
        _visit_constant_node(value: str) -> str:
            Converts a constant value to an SQL string.
        _visit_multiple_fields_node(multiple_fields_node: MultipleFieldsNode) -> str:
            Visits a multiple fields node and converts it to an SQL string.
        _visit_member_access_node(member_access_node: MemberAccessNode) -> str:
            Visits a member access node and converts it to an SQL string.
        _visit_property_access_node(property_access_node: PropertyAccessNode) -> str:
            Visits a property access node and converts it to an SQL string.
        _visit_index_property(property_path: str) -> str:
            Abstract method to handle index properties. Must be implemented in the child class.
        _visit_method_calling(property_path: str, method_name: str, method_args: List[str]) -> str:
            Visits a method calling node and converts it to an SQL string.
        _visit_contains_method_calling(property_path: str, method_args: List[str]) -> str:
            Abstract method to handle 'contains' method calls. Must be implemented in the child class.
        _visit_startwith_method_calling(property_path: str, method_args: List[str]) -> str:
            Abstract method to handle 'startsWith' method calls. Must be implemented in the child class.
        _visit_endswith_method_calling(property_path: str, method_args: List[str]) -> str:
            Abstract method to handle 'endsWith' method calls. Must be implemented in the child class.
        _visit_unary_node(unary_node: UnaryNode) -> str:
            Visits a unary node and converts it to an SQL string.
        _visit_unary_not(operand: str) -> str:
            Converts a NOT operation to an SQL string.
        """

    def __init__(self, dialect: Dialect, properties_metadata: PropertiesMetadata):
        super().__init__()
        self.__literal_proc = String("").literal_processor(dialect=dialect)
        self.properties_mapper = PropertiesMapper(properties_metadata)

    def convert_to_sql_str(self, cel: str) -> str:
        """
        Converts a CEL (Common Expression Language) expression to an SQL string.
        Args:
            cel (str): The CEL expression to convert.
        Returns:
            str: The resulting SQL string. Returns an empty string if the input CEL expression is empty.
        Raises:
            CelToSqlException: If there is an error parsing the CEL expression, mapping properties, or building the SQL filter.
        """

        if not cel:
            return ""

        try:
            original_query = CelToAstConverter.convert_to_ast(cel)
        except CELParseError as e:
            raise CelToSqlException(f"Error parsing CEL expression: {str(e)}") from e

        try:
            with_mapped_props = self.properties_mapper.map_props_in_ast(original_query)
        except PropertiesMappingException as e:
            raise CelToSqlException(f"Error while mapping columns: {str(e)}") from e

        if not with_mapped_props:
            return ""

        try:
            sql_filter = self.__build_sql_filter(with_mapped_props, [])
            return sql_filter
        except NotImplementedError as e:
            raise CelToSqlException(f"Error while converting CEL expression tree to SQL: {str(e)}") from e

    def literal_proc(self, value: Any) -> str:
        if isinstance(value, str):
            return self.__literal_proc(value)

        return f"'{str(value)}'"

    def _get_default_value_for_type(self, type: type) -> str:
        if type is str or type is NoneType:
            return "'__@NULL@__'" # This is a workaround for handling NULL values in SQL

        return "NULL"

    def __build_sql_filter(self, abstract_node: Node, stack: list[Node]) -> str:
        stack.append(abstract_node)
        result = None

        if isinstance(abstract_node, ParenthesisNode):
            result = self._visit_parentheses(
                self.__build_sql_filter(abstract_node.expression, stack)
            )

        if isinstance(abstract_node, LogicalNode):
            result = self._visit_logical_node(abstract_node, stack)

        if isinstance(abstract_node, ComparisonNode):
            result = self._visit_comparison_node(abstract_node, stack)

        if isinstance(abstract_node, MemberAccessNode):
            result = self._visit_member_access_node(abstract_node, stack)

        if isinstance(abstract_node, UnaryNode):
            result = self._visit_unary_node(abstract_node, stack)

        if isinstance(abstract_node, ConstantNode):
            result = self._visit_constant_node(abstract_node.value)

        if isinstance(abstract_node, MultipleFieldsNode):
            result = self._visit_multiple_fields_node(abstract_node, None, stack)

        if result:
            stack.pop()
            return result

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def json_extract(self, column: str, path: str) -> str:
        raise NotImplementedError("Extracting JSON is not implemented. Must be implemented in the child class.")

    def json_extract_as_text(self, column: str, path: str) -> str:
        raise NotImplementedError("Extracting JSON is not implemented. Must be implemented in the child class.")

    def coalesce(self, args: List[str]) -> str:
        raise NotImplementedError("COALESCE is not implemented. Must be implemented in the child class.")

    def cast(self, expression_to_cast: str, to_type: type) -> str:
        raise NotImplementedError("CAST is not implemented. Must be implemented in the child class.")

    def _visit_parentheses(self, node: str) -> str:
        return f"({node})"

    # region Logical Visitors
    def _visit_logical_node(self, logical_node: LogicalNode, stack: list[Node]) -> str:
        left = self.__build_sql_filter(logical_node.left, stack)
        right = self.__build_sql_filter(logical_node.right, stack)

        if logical_node.operator == LogicalNode.AND:
            return self._visit_logical_and(left, right)
        elif logical_node.operator == LogicalNode.OR:
            return self._visit_logical_or(left, right)

        raise NotImplementedError(
            f"{logical_node.operator} logical operator is not supported yet"
        )

    def _visit_logical_and(self, left: str, right: str) -> str:
        return f"({left} AND {right})"

    def _visit_logical_or(self, left: str, right: str) -> str:
        return f"({left} OR {right})"

    # endregion

    # region Comparison Visitors
    def _visit_comparison_node(self, comparison_node: ComparisonNode, stack: list[Node]) -> str:
        first_operand = None
        second_operand = None

        if comparison_node.operator == ComparisonNode.IN:
            return self._visit_in(
                comparison_node.first_operand,
                (
                    comparison_node.second_operand
                    if isinstance(comparison_node.second_operand, list)
                    else [comparison_node.second_operand]
                ),
                stack,
            )

        if isinstance(comparison_node.second_operand, ConstantNode):
            second_operand = self._visit_constant_node(comparison_node.second_operand.value)

            if isinstance(comparison_node.first_operand, JsonPropertyAccessNode):
                first_operand = self.cast(self.__build_sql_filter(comparison_node.first_operand, stack), type(comparison_node.second_operand.value))

            if isinstance(comparison_node.first_operand, MultipleFieldsNode):
                first_operand = self._visit_multiple_fields_node(comparison_node.first_operand, type(comparison_node.second_operand.value), stack)

        if first_operand is None:
            first_operand = self.__build_sql_filter(comparison_node.first_operand, stack)

        if second_operand is None:
            second_operand = self.__build_sql_filter(comparison_node.second_operand, stack)

        if comparison_node.operator == ComparisonNode.EQ:
            result = self._visit_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.NE:
            result = self._visit_not_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.GT:
            result = self._visit_greater_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.GE:
            result = self._visit_greater_than_or_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.LT:
            result = self._visit_less_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.LE:
            result = self._visit_less_than_or_equal(first_operand, second_operand)
        else:
            raise NotImplementedError(
                f"{comparison_node.operator} comparison operator is not supported yet"
            )

        return result

    def _visit_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} = {second_operand}"

    def _visit_not_equal(self, first_operand: str, second_operand: str) -> str:
        if second_operand == "NULL":
            return f"{first_operand} IS NOT NULL"

        return f"{first_operand} != {second_operand}"

    def _visit_greater_than(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} > {second_operand}"

    def _visit_greater_than_or_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} >= {second_operand}"

    def _visit_less_than(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} < {second_operand}"

    def _visit_less_than_or_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} <= {second_operand}"

    def _visit_in(self, first_operand: Node, array: list[ConstantNode], stack: list[Node]) -> str:
        cast_to = type(array[0].value)

        if not all(isinstance(item.value, cast_to) for item in array):
            cast_to = str

        if isinstance(first_operand, PropertyAccessNode):
            first_operand_str = self.cast(self._visit_property_access_node(first_operand, stack), cast_to)
        elif isinstance(first_operand, MultipleFieldsNode):
            first_operand_str = self._visit_multiple_fields_node(first_operand, cast_to, stack)
        else:
            first_operand_str = self.__build_sql_filter(first_operand, stack)

        return f"{first_operand_str} in ({ ', '.join([self._visit_constant_node(c.value) for c in array])})"

    # endregion

    def _visit_constant_node(self, value: str) -> str:
        if value is None:
            return self._get_default_value_for_type(NoneType)
        if isinstance(value, str):
            return self.literal_proc(value)
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) or isinstance(value, int):
            return str(value)

        raise NotImplementedError(f"{type(value).__name__} constant type is not supported yet. Consider implementing this support in child class.")

    # region Member Access Visitors
    def _visit_multiple_fields_node(self, multiple_fields_node: MultipleFieldsNode, cast_to: type, stack) -> str:
        coalesce_args = []

        for item in multiple_fields_node.fields:
            arg = self._visit_property_access_node(item, stack)
            if isinstance(item, JsonPropertyAccessNode) and cast_to:
                arg = self.cast(arg, cast_to)
            coalesce_args.append(arg)

        if len(coalesce_args) == 1:
            return coalesce_args[0]

        coalesce_args.append(self._get_default_value_for_type(cast_to))

        return self.coalesce(coalesce_args)

    def _visit_member_access_node(self, member_access_node: MemberAccessNode, stack) -> str:
        if isinstance(member_access_node, PropertyAccessNode):
            if member_access_node.is_function_call():
                method_access_node = member_access_node.get_method_access_node()
                return self._visit_method_calling(
                   self._visit_property_access_node(member_access_node, stack),
                    method_access_node.member_name,
                    method_access_node.args,
                )

            return self._visit_property_access_node(member_access_node, stack)

        if isinstance(member_access_node, MethodAccessNode):
            return self._visit_method_calling(
                None, member_access_node.member_name, member_access_node.args
            )

        raise NotImplementedError(
            f"{type(member_access_node).__name__} member access node is not supported yet"
        )

    def _visit_property_access_node(self, property_access_node: PropertyAccessNode, stack: list[Node]) -> str:
        if (isinstance(property_access_node, JsonPropertyAccessNode)):
            return self.json_extract_as_text(property_access_node.json_property_name, property_access_node.property_to_extract)

        return property_access_node.get_property_path()

    def _visit_index_property(self, property_path: str) -> str:
        raise NotImplementedError("Index property is not supported yet")
    # endregion

    # region Method Calling Visitors
    def _visit_method_calling(
        self, property_path: str, method_name: str, method_args: List[str]
    ) -> str:
        if method_name == "contains":
            return self._visit_contains_method_calling(property_path, method_args)

        if method_name == "startsWith":
            return self._visit_starts_with_method_calling(property_path, method_args)

        if method_name == "endsWith":
            return self._visit_ends_with_method_calling(property_path, method_args)

        raise NotImplementedError(f"'{method_name}' method is not supported")

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError("'contains' method must be implemented in the child class")

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError("'startsWith' method call must be implemented in the child class")

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError("'endsWith' method call must be implemented in the child class")

    # endregion

    # region Unary Visitors
    def _visit_unary_node(self, unary_node: UnaryNode, stack: list[Node]) -> str:
        if unary_node.operator == UnaryNode.NOT:
            return self._visit_unary_not(self.__build_sql_filter(unary_node.operand, stack))

        raise NotImplementedError(
            f"{unary_node.operator} unary operator is not supported yet"
        )

    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"

    # endregion
