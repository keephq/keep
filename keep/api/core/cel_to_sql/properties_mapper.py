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

from keep.api.core.cel_to_sql.properties_metadata import JsonMapping, PropertiesMetadata, SimpleMapping

class JsonPropertyAccessNode(PropertyAccessNode):
    def __init__(self, json_property_name: str, property_to_extract: str, method_access_node: MethodAccessNode):
        super().__init__(f"JSON({json_property_name}).{property_to_extract}", method_access_node)
        self.json_property_name = json_property_name
        self.property_to_extract = property_to_extract

class MultipleFieldsNode(Node):
    def __init__(self, fields: list[PropertyAccessNode]):
        self.fields = fields

class PropertiesMappingException(Exception):
    pass

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

        property_metadata = self.properties_metadata.get_property_metadata(
            comparison_node.first_operand.get_property_path()
        )

        if not property_metadata:
            raise PropertiesMappingException(
                f'Missing mapping configuration for property "{comparison_node.first_operand.get_property_path()}" '
                f'while processing the comparison node: "{comparison_node}".'
            )

        result = []
        for mapping in property_metadata:
            property_access_node = self._create_property_access_node(mapping, None)
            result.append(property_access_node)

        return ComparisonNode(
                MultipleFieldsNode(result),
                comparison_node.operator,
                comparison_node.second_operand,
            )

    def _visit_member_access_node(self, member_access_node: MemberAccessNode) -> Node:
        if (
            isinstance(member_access_node, PropertyAccessNode)
            and member_access_node.is_function_call()
        ):
            property_metadata = self.properties_metadata.get_property_metadata(
                member_access_node.get_property_path()
            )

            if not property_metadata:
                raise PropertiesMappingException(
                    f'Missing mapping configuration for property "{member_access_node.get_property_path()}" '
                    f'while processing the comparison node: "{member_access_node}".'
                )

            result = None
            for mapping in property_metadata:
                method_access_node = member_access_node.get_method_access_node().copy()
                current_node_result = self._create_property_access_node(
                    mapping, method_access_node
                )
                current_node_result = LogicalNode(
                    left=ComparisonNode(
                        first_operand = self._create_property_access_node(mapping, None),
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
    
    def _create_property_access_node(self, mapping, method_access_node: MethodAccessNode) -> Node:
        if (isinstance(mapping, JsonMapping)):
            return JsonPropertyAccessNode(mapping.json_prop, mapping.prop_in_json, method_access_node)
        
        if (isinstance(mapping, SimpleMapping)):
            return PropertyAccessNode(mapping.map_to, method_access_node)
        
        raise NotImplementedError(f"Mapping type {type(mapping).__name__} is not supported yet")
