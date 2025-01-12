from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ConstantNode,
    LogicalNode,
    MemberAccessNode,
    MethodAccessNode,
    Node,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
)


class PropertiesMapper:
    def __init__(self, known_fields_mapping: dict):
        self.known_fields_mapping = known_fields_mapping

    def map_props_in_ast(self, abstract_node: Node) -> Node:
        if isinstance(abstract_node, ParenthesisNode):
            return self.map_props_in_ast(abstract_node.expression)

        if isinstance(abstract_node, LogicalNode):
            return LogicalNode(
                left=self.map_props_in_ast(abstract_node.left),
                operator=abstract_node.operator,
                right=self.map_props_in_ast(abstract_node.right),
            )

        if isinstance(abstract_node, ComparisonNode):
            return self.__visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            return self._visit_member_access_node(abstract_node)

        if isinstance(abstract_node, UnaryNode):
            return UnaryNode(abstract_node.operator, self.map_props_in_ast(abstract_node.operand))

        if isinstance(abstract_node, ConstantNode):
            return abstract_node

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )
    
    def __get_prop_mapping(self, prop_path: str) -> list[str]:
        if prop_path in self.known_fields_mapping:
            return [self.known_fields_mapping[prop_path].get("field")]
        
        field_mapping = None

        if prop_path in self.known_fields_mapping:
            field_mapping = self.known_fields_mapping.get(prop_path)

        if "*" in self.known_fields_mapping:
            field_mapping = self.known_fields_mapping.get("*")

        if field_mapping:

            if "take_from" in field_mapping:
                result = []
                for take_from in field_mapping.get("take_from"):
                    if field_mapping.get("type") == "json":
                        result.append(f'JSON({take_from}).{prop_path}')
                return result
            
            if "field" in field_mapping:
                return [field_mapping.get("field")]

        return [prop_path]


    def __visit_comparison_node(self, comparison_node: ComparisonNode) -> Node:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return comparison_node

        result: str = None
        for mapping in self.__get_prop_mapping(
            comparison_node.first_operand.get_property_path()
        ):
            property_access_node = PropertyAccessNode(mapping, None)
            
            current_node_result = ComparisonNode(
                property_access_node,
                comparison_node.operator,
                comparison_node.second_operand,
            )
            current_node_result = LogicalNode(
                left=ComparisonNode(
                        property_access_node,
                        ComparisonNode.NE,
                        ConstantNode(None),
                    ),
                operator=LogicalNode.AND,
                right=current_node_result
            )
            if result is None:
                result = current_node_result
                continue

            result = LogicalNode(
                left=result,
                operator=LogicalNode.OR,
                right=current_node_result,
            )

        return result

    def _visit_member_access_node(self, member_access_node: MemberAccessNode) -> Node:
        if (
            isinstance(member_access_node, PropertyAccessNode)
            and member_access_node.is_function_call()
        ):
            result = None
            for mapping in self.__get_prop_mapping(
                member_access_node.get_property_path()
            ):
                method_access_node = member_access_node.get_method_access_node().copy()
                property_access_node = PropertyAccessNode(
                    mapping,
                    MethodAccessNode(
                        method_access_node.member_name,
                        method_access_node.args,
                    ),
                )
                property_access_node = LogicalNode(
                    left=ComparisonNode(
                        first_operand = PropertyAccessNode(mapping, None),
                        operator = ComparisonNode.NE,
                        second_operand = ConstantNode(None),
                    ),
                    operator=LogicalNode.AND,
                    right=property_access_node,
                )

                if result is None:
                    result = property_access_node
                    continue

                result = LogicalNode(
                    left=result,
                    operator=LogicalNode.OR,
                    right=property_access_node,
                )

            return result

        return member_access_node
