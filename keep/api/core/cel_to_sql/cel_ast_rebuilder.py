from keep.api.core.cel_to_sql.ast_nodes import (
    ConstantNode,
    MemberAccessNode,
    Node,
    LogicalNode,
    ComparisonNode,
    PropertyAccessNode,
    UnaryNode,
    ParenthesisNode,
)

from keep.api.core.cel_to_sql.properties_mapper import (
    JsonPropertyAccessNode,
    MultipleFieldsNode,
)


class CelAstRebuilder:
    def __init__(self, cel_ast: Node):
        self.cel_ast = cel_ast
        super().__init__()

    def rebuild(self) -> Node:
        self.stack = []
        result = self.__visit_ast(self.cel_ast)
        self.stack = []
        return result

    def __visit_ast(self, abstract_node: Node) -> Node:
        result = None

        if abstract_node is None:
            return None

        if isinstance(abstract_node, ParenthesisNode):
            result = ParenthesisNode(
                expression=self.__visit_ast(abstract_node.left),
            )

        if isinstance(abstract_node, LogicalNode):
            result = LogicalNode(
                left=self.__visit_ast(abstract_node.left),
                operator=abstract_node.operator,
                right=self.__visit_ast(abstract_node.right),
            )

        if isinstance(abstract_node, ComparisonNode):
            result = self._visit_comparison_node(abstract_node)

        if isinstance(abstract_node, PropertyAccessNode):
            result = abstract_node

        if isinstance(abstract_node, UnaryNode):
            if abstract_node.operator == UnaryNode.NOT:
                result = self._visit_unary_not_node(abstract_node)
            else:
                result = UnaryNode(
                    operator=abstract_node.operator,
                    operand=self.__visit_ast(abstract_node.operand),
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

    def _visit_unary_not_node(self, unary_node: UnaryNode) -> Node:
        if (
            isinstance(unary_node.operand, UnaryNode)
            and unary_node.operand.operator == UnaryNode.NOT
        ):
            return self.__visit_ast(unary_node.operand.operand)

        if isinstance(unary_node.operand, PropertyAccessNode):
            return LogicalNode(
                left=ComparisonNode(
                    unary_node.operand,
                    ComparisonNode.NE,
                    ConstantNode(None),
                ),
                operator=LogicalNode.AND,
                right=LogicalNode(
                    left=ComparisonNode(
                        unary_node.operand,
                        ComparisonNode.NE,
                        ConstantNode(0),
                    ),
                    operator=LogicalNode.AND,
                    right=LogicalNode(
                        left=ComparisonNode(
                            unary_node.operand,
                            ComparisonNode.NE,
                            ConstantNode(False),
                        ),
                        operator=LogicalNode.AND,
                        right=ComparisonNode(
                            unary_node.operand,
                            ComparisonNode.NE,
                            ConstantNode(""),
                        ),
                    ),
                ),
            )

        return unary_node

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
