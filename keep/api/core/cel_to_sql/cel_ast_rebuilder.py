from keep.api.core.cel_to_sql.ast_nodes import (
    ConstantNode,
    MemberAccessNode,
    Node,
    LogicalNode,
    ComparisonNode,
    UnaryNode,
    ParenthesisNode,
)

from keep.api.core.cel_to_sql.properties_mapper import (
    MultipleFieldsNode,
)


class CelAstRebuilder:
    def __init__(self, cel_ast: Node):
        self.cel_ast = cel_ast
        super().__init__()

    def rebuild(self) -> Node:
        self.stack = []
        result = self.__build_sql_filter(self.cel_ast)
        self.stack = []
        return result

    def __build_sql_filter(self, abstract_node: Node) -> Node:
        result = None

        if abstract_node is None:
            return None

        if isinstance(abstract_node, ParenthesisNode):
            result = ParenthesisNode(
                expression=self.__build_sql_filter(abstract_node.left),
            )

        if isinstance(abstract_node, LogicalNode):
            result = LogicalNode(
                left=self.__build_sql_filter(abstract_node.left),
                operator=abstract_node.operator,
                right=self.__build_sql_filter(abstract_node.right),
            )

        if isinstance(abstract_node, ComparisonNode):
            result = self._visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            result = abstract_node

        if isinstance(abstract_node, UnaryNode):
            result = UnaryNode(
                operator=abstract_node.operator,
                operand=self.__build_sql_filter(abstract_node.operand),
            )

        if isinstance(abstract_node, ConstantNode):
            result = abstract_node

        if isinstance(abstract_node, MultipleFieldsNode):
            result = abstract_node

        if result:
            return result

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def _visit_parentheses(self, node: str) -> Node:
        return f"({node})"

    # region Comparison Visitors
    def _visit_comparison_node(self, comparison_node: ComparisonNode) -> Node:
        if comparison_node.operator == ComparisonNode.IN:
            return self._visit_in(comparison_node)

        return comparison_node

    def _visit_in(self, in_node: ComparisonNode) -> Node:
        is_none_in_args = None in in_node.second_operand
        filtered_args = []
        nodes = []

        for item in in_node.second_operand:
            is_none_in_args = item.value is None

            if item.value is not None:
                filtered_args.append(item)

        nodes = []

        if len(filtered_args) > 1:
            nodes.append(
                ComparisonNode(
                    operator=ComparisonNode.IN,
                    first_operand=in_node.first_operand,
                    second_operand=filtered_args,
                )
            )

        if is_none_in_args:
            nodes.append(
                ComparisonNode(
                    operator=ComparisonNode.EQ,
                    first_operand=in_node.first_operand,
                    second_operand=ConstantNode(value=None),
                )
            )

        final_node = nodes[0]

        for query in nodes[1:]:
            final_node = LogicalNode(
                left=final_node,
                operator=LogicalNode.OR,
                right=query,
            )

        return final_node

    # endregion

    # def _visit_constant_node(self, value: Any) -> str:
    #     if value is None:
    #         return "NULL"
    #     if isinstance(value, str):
    #         return self.literal_proc(value)
    #     if isinstance(value, bool):
    #         return str(value).lower()
    #     if isinstance(value, float) or isinstance(value, int):
    #         return str(value)

    #     raise NotImplementedError(f"{type(value).__name__} constant type is not supported yet. Consider implementing this support in child class.")

    # # region Member Access Visitors
    # def _visit_multiple_fields_node(self, multiple_fields_node: MultipleFieldsNode, cast_to: type, stack) -> str:
    #     coalesce_args = []

    #     for item in multiple_fields_node.fields:
    #         arg = self._visit_property_access_node(item, stack)
    #         if isinstance(item, JsonPropertyAccessNode) and cast_to:
    #             arg = self.cast(arg, cast_to)
    #         coalesce_args.append(arg)

    #     if len(coalesce_args) == 1:
    #         return coalesce_args[0]

    #     return self.coalesce(coalesce_args)

    # def _visit_member_access_node(self, member_access_node: MemberAccessNode, stack) -> str:
    #     if isinstance(member_access_node, PropertyAccessNode):
    #         if member_access_node.is_function_call():
    #             method_access_node = member_access_node.get_method_access_node()
    #             return self._visit_method_calling(
    #                self._visit_property_access_node(member_access_node, stack),
    #                 method_access_node.member_name,
    #                 method_access_node.args,
    #             )

    #         return self._visit_property_access_node(member_access_node, stack)

    #     if isinstance(member_access_node, MethodAccessNode):
    #         return self._visit_method_calling(
    #             None, member_access_node.member_name, member_access_node.args
    #         )

    #     raise NotImplementedError(
    #         f"{type(member_access_node).__name__} member access node is not supported yet"
    #     )
    # endregion
