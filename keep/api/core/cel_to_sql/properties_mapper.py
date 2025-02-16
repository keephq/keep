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

from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertiesMetadata,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)

class JsonPropertyAccessNode(PropertyAccessNode):
    """
    A node representing access to a property within a JSON object.

    This class extends PropertyAccessNode to allow for the extraction of a specific property
    from a JSON object using a method access node.

    Attributes:
        json_property_name (str): The name of the JSON property to access.
        property_to_extract (str): The specific property to extract from the JSON object.
        method_access_node (MethodAccessNode): The method access node used for extraction. (*.contains, *.startsWith, etc)
    """
    def __init__(self, json_property_name: str, property_to_extract: str, method_access_node: MethodAccessNode):
        super().__init__(f"JSON({json_property_name}).{property_to_extract}", method_access_node)
        self.json_property_name = json_property_name
        self.property_to_extract = property_to_extract

class MultipleFieldsNode(Node):
    """
    A node representing multiple fields in a property access structure.
    It's used when for example one being queried field refers to multiple fields in the database.

    Attributes:
        fields (list[PropertyAccessNode]): A list of PropertyAccessNode instances representing the fields.
    
    Args:
        fields (list[PropertyAccessNode]): A list of PropertyAccessNode instances to initialize the node with.
    """
    def __init__(self, fields: list[PropertyAccessNode]):
        self.fields = fields

class PropertiesMappingException(Exception):
    """
    Exception raised for errors in the properties mapping process.

    Attributes:
        message (str): Explanation of the error.
    """
    pass

class PropertiesMapper:
    """
    A class to map properties in an abstract syntax tree (AST) based on provided metadata.
    Attributes:
        properties_metadata (PropertiesMetadata): Metadata containing property mappings.
    Methods:
        __init__(properties_metadata: PropertiesMetadata):
            Initializes the PropertiesMapper with the given properties metadata.
        map_props_in_ast(abstract_node: Node) -> Node:
            Maps properties in the given AST node based on the properties metadata.
        __visit_comparison_node(comparison_node: ComparisonNode) -> Node:
            Visits and processes a comparison node, mapping properties as needed.
        _visit_member_access_node(member_access_node: MemberAccessNode) -> Node:
            Visits and processes a member access node, mapping properties as needed.
        _create_property_access_node(mapping, method_access_node: MethodAccessNode) -> Node:
            Creates a property access node based on the given mapping and method access node.
    """
    def __init__(self, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata

    def map_props_in_ast(self, abstract_node: Node) -> Node:
        return self.__visit_nodes(abstract_node)

    def __visit_nodes(self, abstract_node: Node) -> Node:
        if isinstance(abstract_node, ParenthesisNode):
            return self.map_props_in_ast(abstract_node.expression)

        if isinstance(abstract_node, LogicalNode):
            left = self.map_props_in_ast(abstract_node.left)
            right = self.map_props_in_ast(abstract_node.right)

            if left is None:
                return right

            if right is None:
                return left

            return LogicalNode(
                left=left,
                operator=abstract_node.operator,
                right=right,
            )

        if isinstance(abstract_node, ComparisonNode):
            return self.__visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            return self._visit_member_access_node(abstract_node)

        if isinstance(abstract_node, UnaryNode):
            operand = self.map_props_in_ast(abstract_node.operand)

            if operand is None:
                return UnaryNode(abstract_node.operator, ConstantNode(True))

            return UnaryNode(abstract_node.operator, self.map_props_in_ast(abstract_node.operand))

        if isinstance(abstract_node, ConstantNode):
            return abstract_node

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def __visit_comparison_node(self, comparison_node: ComparisonNode) -> Node:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return comparison_node

        first_operand, property_metadata = self._map_property(
            comparison_node.first_operand
        )
        comparison_node = ComparisonNode(
            first_operand,
            comparison_node.operator,
            comparison_node.second_operand,
        )
        return self._modify_comparison_node_based_on_mapping(
            comparison_node, property_metadata
        )

    def _visit_member_access_node(self, member_access_node: MemberAccessNode) -> Node:
        if (
            isinstance(member_access_node, PropertyAccessNode)
            and not member_access_node.is_function_call()
        ):
            # in case expression is just property access node
            # it will behave like !!property in JS
            # converting queried property to boolean and evaluate as boolean
            mapped_prop, _ = self._map_property(member_access_node)
            return LogicalNode(
                left=ComparisonNode(
                    mapped_prop,
                    ComparisonNode.NE,
                    ConstantNode(None),
                ),
                operator=LogicalNode.AND,
                right=LogicalNode(
                    left=ComparisonNode(
                        mapped_prop,
                        ComparisonNode.NE,
                        ConstantNode("0"),
                    ),
                    operator=LogicalNode.AND,
                    right=LogicalNode(
                        left=ComparisonNode(
                            mapped_prop,
                            ComparisonNode.NE,
                            ConstantNode(False),
                        ),
                        operator=LogicalNode.AND,
                        right=ComparisonNode(
                            mapped_prop,
                            ComparisonNode.NE,
                            ConstantNode(""),
                        ),
                    ),
                ),
            )

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
            for mapping in property_metadata.field_mappings:
                method_access_node = member_access_node.get_method_access_node().copy()
                current_node_result = self._create_property_access_node(
                    mapping, method_access_node
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

    def _modify_comparison_node_based_on_mapping(
        self, comparison_node: ComparisonNode, mapping: PropertyMetadataInfo
    ):
        """
        Modifies a comparison node based on the provided property metadata mapping.

        This method adjusts the comparison node if the property being compared has
        enumerated values. Specifically, it handles cases where the comparison
        operator is one of the following: GE (greater than or equal to), GT (greater
        than), LE (less than or equal to), or LT (less than). If the second operand
        of the comparison node is not in the enumerated values, it modifies the
        comparison to use the IN operator with the enumerated values. Additionally,
        it handles ranges based on the comparison operator and the index of the
        second operand in the enumerated values.

        Args:
            comparison_node (ComparisonNode): The comparison node to be modified.
            mapping (PropertyMetadataInfo): The property metadata information that
                includes enumerated values.

        Returns:
            ComparisonNode: The modified comparison node, or the original comparison
            node if no modifications are necessary.
        """
        if mapping.enum_values:
            if comparison_node.operator in [
                ComparisonNode.GE,
                ComparisonNode.GT,
                ComparisonNode.LE,
                ComparisonNode.LT,
            ]:
                if comparison_node.second_operand.value not in mapping.enum_values:
                    if comparison_node.operator in [
                        ComparisonNode.LT,
                        ComparisonNode.LE,
                    ]:
                        return UnaryNode(
                            UnaryNode.NOT,
                            ComparisonNode(
                                comparison_node.first_operand,
                                ComparisonNode.IN,
                                [ConstantNode(item) for item in mapping.enum_values],
                            ),
                        )
                    else:
                        return ComparisonNode(
                            comparison_node.first_operand,
                            ComparisonNode.IN,
                            [ConstantNode(item) for item in mapping.enum_values],
                        )

                index = mapping.enum_values.index(comparison_node.second_operand.value)
                ranges = {
                    ComparisonNode.GT: [index + 1, None],
                    ComparisonNode.GE: [index, None],
                    ComparisonNode.LT: [index, None],
                    ComparisonNode.LE: [index + 1, None],
                }

                start_index, end_index = ranges[comparison_node.operator]

                if (
                    comparison_node.operator == ComparisonNode.LE
                    and start_index >= len(mapping.enum_values)
                ):
                    # it handles the case when queried value is the last in enum
                    # and hence any value is applicable
                    # and there is no need to even do filtering
                    return None

                if (
                    comparison_node.operator == ComparisonNode.GT
                    and start_index >= len(mapping.enum_values)
                ):
                    # nothig could be greater than the last value in enum
                    # so it will always return False
                    return ConstantNode(False)

                result = ComparisonNode(
                    comparison_node.first_operand,
                    ComparisonNode.IN,
                    [
                        ConstantNode(item)
                        for item in mapping.enum_values[start_index:end_index]
                    ],
                )

                if comparison_node.operator in [ComparisonNode.LT, ComparisonNode.LE]:
                    result = UnaryNode(UnaryNode.NOT, result)
                return result

        return comparison_node

    def _create_property_access_node(self, mapping, method_access_node: MethodAccessNode) -> Node:
        if isinstance(mapping, JsonFieldMapping):
            return JsonPropertyAccessNode(mapping.json_prop, mapping.prop_in_json, method_access_node)

        if isinstance(mapping, SimpleFieldMapping):
            return PropertyAccessNode(mapping.map_to, method_access_node)

        raise NotImplementedError(f"Mapping type {type(mapping).__name__} is not supported yet")

    def _map_property(
        self, property_access_node: PropertyAccessNode
    ) -> tuple[MultipleFieldsNode, PropertyMetadataInfo]:
        property_metadata = self.properties_metadata.get_property_metadata(
            property_access_node.get_property_path()
        )

        if not property_metadata:
            raise PropertiesMappingException(
                f'Missing mapping configuration for property "{property_access_node.get_property_path()}"'
            )

        result = []

        for mapping in property_metadata.field_mappings:
            property_access_node = self._create_property_access_node(mapping, None)
            result.append(property_access_node)
        return (
            MultipleFieldsNode(result) if len(result) > 1 else result[0]
        ), property_metadata
