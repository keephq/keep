from typing import List
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


class SqlField:
    def __init__(self, field_name: str, field_type: str, take_from_json_in=None):
        self.field_name = field_name
        self.field_type = field_type
        self.take_from_json_in = take_from_json_in

    def __str__(self):
        return f"{self.field_name} {self.field_type}"


class BaseCelToSqlProvider:
    # def __init__(self, sql_fields: List[SqlField]):
    #     self._sql_fields_dict = {field.field_name: field for field in sql_fields}

    def convert_to_sql_str(self, cel: str, base_query: str) -> str:
        """
        Converts a CEL (Common Expression Language) string to an SQL string.

        Args:
            cel (str): The CEL expression to convert.
            base_query (str): The base SQL query to append the converted CEL expression to.

        Returns:
            str: The resulting SQL query string with the CEL expression converted to SQL.
        """
        cell_ast = CelToAstConverter.convert_to_ast(cel)


        return base_query + " WHERE " + self._recursive_visit(cell_ast)

    def _recursive_visit(self, abstract_node: Node) -> str:
        if isinstance(abstract_node, ParenthesisNode):
            return self._visit_parentheses(
                self._recursive_visit(abstract_node.expression)
            )

        if isinstance(abstract_node, LogicalNode):
            return self._visit_logical_node(abstract_node)

        if isinstance(abstract_node, ComparisonNode):
            return self._visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            return self._visit_member_access_node(abstract_node)

        if isinstance(abstract_node, UnaryNode):
            return self._visit_unary_node(abstract_node)

        if isinstance(abstract_node, ConstantNode):
            return self._visit_constant_node(abstract_node.value)

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def _visit_parentheses(self, node: str) -> str:
        return f"({node})"

    # region Logical Visitors
    def _visit_logical_node(self, logical_node: LogicalNode) -> str:
        left = self._recursive_visit(logical_node.left)
        right = self._recursive_visit(logical_node.right)

        if logical_node.operator == LogicalNode.AND:
            return self._visit_logical_and(left, right)
        elif logical_node.operator == LogicalNode.OR:
            return self._visit_logical_or(left, right)

        raise NotImplementedError(
            f"{logical_node.operator} logical operator is not supported yet"
        )

    def _visit_logical_and(self, left: str, right: str) -> str:
        return f"{left} AND {right}"

    def _visit_logical_or(self, left: str, right: str) -> str:
        return f"{left} OR {right}"

    # endregion

    # region Comparison Visitors
    def _visit_comparison_node(self, comparison_node: ComparisonNode) -> str:
        first_operand = self._recursive_visit(comparison_node.firstOperand)
        second_operand = self._recursive_visit(comparison_node.secondOperand)

        if comparison_node.operator == ComparisonNode.EQ:
            return self._visit_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.NE:
            return self._visit_not_equal(first_operand, second_operand)

        raise NotImplementedError(
            f"{comparison_node.operator} comparison operator is not supported yet"
        )

    def _visit_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} = {second_operand}"

    def _visit_not_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} != {second_operand}"

    # endregion

    def _visit_constant_node(self, value: str) -> str:
        return f"'{str(value)}'"

    # region Member Access Visitors
    def _visit_member_access_node(self, member_access_node: MemberAccessNode) -> str:
        if isinstance(member_access_node, PropertyAccessNode):
            if member_access_node.is_function_call():
                method_access_node = member_access_node.get_method_access_node()
                return self._visit_method_calling(
                    member_access_node.get_property_path(),
                    method_access_node.member_name,
                    method_access_node.args,
                )

            return self._visit_property(member_access_node.get_property_path())

        if isinstance(member_access_node, MethodAccessNode):
            return self._visit_method_calling(
                None, member_access_node.member_name, member_access_node.args
            )
        
        raise NotImplementedError(
            f"{type(member_access_node).__name__} member access node is not supported yet"
        )
        
    def _visit_property(self, property_path: str) -> str:
        return property_path
    # endregion

    # region Method Calling Visitors
    def _visit_method_calling(
        self, property_path: str, method_name: str, method_args: List[str]
    ) -> str:
        if method_name == "contains":
            return self._visit_contains_method_calling(property_path, method_args)

        if method_name == "startsWith":
            return self._visit_startwith_method_calling(property_path, method_args)

        if method_name == "endsWith":
            return self._visit_endswith_method_calling(property_path, method_args)

        raise NotImplementedError(f"'{method_name}' method is not supported")

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        raise NotImplementedError("'contains' method call is not supported")

    def _visit_startwith_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        raise NotImplementedError("'startswith' method call is not supported")

    def _visit_endswith_method_calling(
        self, property_path: str, method_args: List[str]
    ) -> str:
        raise NotImplementedError("'endswith' method call is not supported")

    # endregion

    # region Unary Visitors
    def _visit_unary_node(self, unary_node: UnaryNode) -> str:
        if unary_node.operator == UnaryNode.NOT:
            return self._visit_unary_not(self._recursive_visit(unary_node.operand))

        raise NotImplementedError(
            f"{unary_node.operator} unary operator is not supported yet"
        )

    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"

    # endregion
