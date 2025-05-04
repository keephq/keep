from typing import Optional
from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    DataType,
    LogicalNode,
    Node,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
    UnaryNodeOperator,
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
    """
    def __init__(
        self,
        json_property_name: str,
        property_to_extract: list[str],
        data_type: DataType,
    ):
        super().__init__(
            member_name=f"JSON({json_property_name}).{property_to_extract}",
        )
        self.json_property_name = json_property_name
        self.property_to_extract = property_to_extract
        self.data_type = data_type

    json_property_name: Optional[str]
    property_to_extract: Optional[list[str]]
    data_type: Optional[DataType]

class MultipleFieldsNode(Node):
    """
    A node representing multiple fields in a property access structure.
    It's used when for example one being queried field refers to multiple fields in the database.

    Attributes:
        fields (list[PropertyAccessNode]): A list of PropertyAccessNode instances representing the fields.
    
    Args:
        fields (list[PropertyAccessNode]): A list of PropertyAccessNode instances to initialize the node with.
    """
    fields: list[PropertyAccessNode]
    data_type: Optional[DataType]

    def __str__(self):
        return f"[{', '.join(['.'.join(field.path) for field in self.fields])}]"


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
        map_props_in_ast(abstract_node: Node) -> tuple[Node, list[PropertyMetadataInfo]]:
            Maps properties in the given AST node based on the properties metadata.
        __visit_nodes(abstract_node: Node, involved_fields: list[PropertyMetadataInfo]) -> Node:
            Recursively visits and processes nodes in the AST, mapping properties as needed.
        __visit_comparison_node(comparison_node: ComparisonNode, involved_fields: list[PropertyMetadataInfo]) -> Node:
            Visits and processes a comparison node, mapping properties as needed.
        _visit_property_access_node(property_access_node: PropertyAccessNode, involved_fields: list[PropertyMetadataInfo]) -> Node:
            Visits and processes a member access node, mapping properties as needed.
        _modify_comparison_node_based_on_mapping(comparison_node: ComparisonNode, mapping: PropertyMetadataInfo) -> Node:
            Modifies a comparison node based on the provided property metadata mapping.
        _create_property_access_node(mapping) -> Node:
            Creates a property access node based on the given mapping and method access node.
        _map_property(property_access_node: PropertyAccessNode) -> tuple[MultipleFieldsNode, PropertyMetadataInfo]:
            Maps a property access node to its corresponding database fields based on the metadata.
    """
    def __init__(self, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata

    def map_props_in_ast(
        self, abstract_node: Node
    ) -> tuple[Node, list[PropertyMetadataInfo]]:
        involved_fields = list[PropertyMetadataInfo]()
        mapped_ast = self.__visit_nodes(abstract_node, involved_fields)
        distinct_involved_fields = {
            field.field_name: field for field in involved_fields
        }
        involved_fields = [value for _, value in distinct_involved_fields.items()]
        return mapped_ast, involved_fields

    def __visit_nodes(
        self, abstract_node: Node, involved_fields: list[PropertyMetadataInfo]
    ) -> Node:
        if isinstance(abstract_node, ParenthesisNode):
            return self.__visit_nodes(abstract_node.expression, involved_fields)

        if isinstance(abstract_node, LogicalNode):
            left = self.__visit_nodes(abstract_node.left, involved_fields)
            right = self.__visit_nodes(abstract_node.right, involved_fields)

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
            return self.__visit_comparison_node(abstract_node, involved_fields)

        if isinstance(abstract_node, PropertyAccessNode):
            return self._visit_property_access_node(abstract_node, involved_fields)

        if isinstance(abstract_node, UnaryNode):
            operand = self.__visit_nodes(abstract_node.operand, involved_fields)

            if operand is None:
                return UnaryNode(
                    operator=abstract_node.operator, operand=ConstantNode(value=True)
                )

            return UnaryNode(
                operator=abstract_node.operator,
                operand=self.__visit_nodes(abstract_node.operand, involved_fields),
            )

        if isinstance(abstract_node, ConstantNode):
            return abstract_node

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def __visit_comparison_node(
        self,
        comparison_node: ComparisonNode,
        involved_fields: list[PropertyMetadataInfo],
    ) -> Node:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return comparison_node

        first_operand, property_metadata = self._map_property(
            comparison_node.first_operand
        )
        involved_fields.append(property_metadata)
        comparison_node = ComparisonNode(
            first_operand=first_operand,
            operator=comparison_node.operator,
            second_operand=comparison_node.second_operand,
        )
        return self._modify_comparison_node_based_on_mapping(
            comparison_node, property_metadata
        )

    def _visit_property_access_node(
        self,
        property_access_node: PropertyAccessNode,
        involved_fields: list[PropertyMetadataInfo],
    ) -> Node:
        # in case expression is just property access node
        # it will behave like !!property in JS
        # converting queried property to boolean and evaluate as boolean
        mapped_prop, property_metadata = self._map_property(property_access_node)
        involved_fields.append(property_metadata)
        return mapped_prop

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
        if not isinstance(comparison_node.second_operand, ConstantNode):
            return comparison_node

        if mapping.enum_values:
            if comparison_node.operator in [
                ComparisonNodeOperator.GE,
                ComparisonNodeOperator.GT,
                ComparisonNodeOperator.LE,
                ComparisonNodeOperator.LT,
            ]:
                if comparison_node.second_operand.value not in mapping.enum_values:
                    if comparison_node.operator in [
                        ComparisonNodeOperator.LT,
                        ComparisonNodeOperator.LE,
                    ]:
                        return UnaryNode(
                            operator=UnaryNodeOperator.NOT,
                            operand=ComparisonNode(
                                first_operand=comparison_node.first_operand,
                                operator=ComparisonNodeOperator.IN,
                                second_operand=[
                                    ConstantNode(value=item)
                                    for item in mapping.enum_values
                                ],
                            ),
                        )
                    else:
                        return ComparisonNode(
                            first_operand=comparison_node.first_operand,
                            operator=ComparisonNodeOperator.IN,
                            second_operand=[
                                ConstantNode(value=item) for item in mapping.enum_values
                            ],
                        )

                index = mapping.enum_values.index(comparison_node.second_operand.value)
                ranges = {
                    ComparisonNodeOperator.GT: [index + 1, None],
                    ComparisonNodeOperator.GE: [index, None],
                    ComparisonNodeOperator.LT: [index, None],
                    ComparisonNodeOperator.LE: [index + 1, None],
                }

                start_index, end_index = ranges[comparison_node.operator]

                if (
                    comparison_node.operator == ComparisonNodeOperator.LE
                    and start_index >= len(mapping.enum_values)
                ):
                    # it handles the case when queried value is the last in enum
                    # and hence any value is applicable
                    # and there is no need to even do filtering
                    return None

                if (
                    comparison_node.operator == ComparisonNodeOperator.GT
                    and start_index >= len(mapping.enum_values)
                ):
                    # nothig could be greater than the last value in enum
                    # so it will always return False
                    return ConstantNode(value=False)

                result = ComparisonNode(
                    first_operand=comparison_node.first_operand,
                    operator=ComparisonNodeOperator.IN,
                    second_operand=[
                        ConstantNode(value=item)
                        for item in mapping.enum_values[start_index:end_index]
                    ],
                )

                if comparison_node.operator in [
                    ComparisonNodeOperator.LT,
                    ComparisonNodeOperator.LE,
                ]:
                    result = UnaryNode(operator=UnaryNodeOperator.NOT, operand=result)
                return result

        return comparison_node

    def _create_property_access_node(self, mapping, data_type: type) -> Node:
        if isinstance(mapping, JsonFieldMapping):
            return JsonPropertyAccessNode(
                json_property_name=mapping.json_prop,
                property_to_extract=mapping.prop_in_json,
                data_type=data_type,
            )

        if isinstance(mapping, SimpleFieldMapping):
            return PropertyAccessNode(
                path=[mapping.map_to],
                data_type=data_type,
            )

        raise NotImplementedError(f"Mapping type {type(mapping).__name__} is not supported yet")

    def _map_property(
        self, property_access_node: PropertyAccessNode
    ) -> tuple[MultipleFieldsNode, PropertyMetadataInfo]:
        property_metadata = self.properties_metadata.get_property_metadata(
            property_access_node.path
        )

        if not property_metadata:
            joined_path = ".".join(property_access_node.path)
            raise PropertiesMappingException(
                f'Missing mapping configuration for property "{joined_path}"'
            )

        result = []

        for mapping in property_metadata.field_mappings:
            property_access_node = self._create_property_access_node(
                mapping, property_metadata.data_type
            )
            result.append(property_access_node)
        return (
            MultipleFieldsNode(fields=result, data_type=property_metadata.data_type)
            if len(result) > 1
            else result[0]
        ), property_metadata
