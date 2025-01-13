import re
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

from keep.api.core.cel_to_sql.properties_metadata import PropertiesMetadata

class JsonPropertyAccessNode(PropertyAccessNode):
    def __init__(self, json_property_name: str, property_to_extract: str, method_access_node: MethodAccessNode):
        super().__init__(f"JSON({json_property_name}).{property_to_extract}", method_access_node)
        self.json_property_name = json_property_name
        self.property_to_extract = property_to_extract


class PropertiesMapper:
    def __init__(self, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata

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

    def __visit_comparison_node(self, comparison_node: ComparisonNode) -> Node:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return comparison_node

        result: str = None
        for mapping in self.properties_metadata.get_property_mapping(
            comparison_node.first_operand.get_property_path()
        ):
            property_access_node = self._visit_property_access_node(PropertyAccessNode(mapping, None))

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
            for mapping in self.properties_metadata.get_property_mapping(
                member_access_node.get_property_path()
            ):
                method_access_node = member_access_node.get_method_access_node().copy()
                current_node_result = self._visit_property_access_node(PropertyAccessNode(
                    mapping,
                    MethodAccessNode(
                        method_access_node.member_name,
                        method_access_node.args,
                    ),
                ))
                current_node_result = LogicalNode(
                    left=ComparisonNode(
                        first_operand = PropertyAccessNode(mapping, None),
                        operator = ComparisonNode.NE,
                        second_operand = ConstantNode(None),
                    ),
                    operator=LogicalNode.AND,
                    right=current_node_result,
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

        return member_access_node

    def _visit_property_access_node(self, property_access_node: PropertyAccessNode) -> Node:
        match = re.compile(r"JSON\((?P<json>[^)]+)\)\.(?P<property_path>.+)").match(
            property_access_node.get_property_path()
        )

        if match:
            json_group = match.group("json")
            property_path_group = match.group("property_path")
            return JsonPropertyAccessNode(json_group, property_path_group, property_access_node.get_method_access_node())

        return property_access_node
