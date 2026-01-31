from __future__ import annotations

from typing import Optional, List, Tuple, Dict

from pydantic import Field

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    DataType,
    LogicalNode,
    LogicalNodeOperator,
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
    Represents access to a nested JSON property.

    path format:
      [<json_column>, <json_key1>, <json_key2>, ...]
    The SQL providers interpret this with json_extract/jsonb ops.
    """
    node_type: str = Field(default="JsonPropertyAccessNode", const=True)
    json_property_name: Optional[str] = None
    property_to_extract: Optional[list[str]] = None

    def __init__(
        self,
        json_property_name: str,
        property_to_extract: list[str],
        data_type: Optional[DataType] = None,
        **kwargs,
    ):
        super().__init__(
            path=[json_property_name] + list(property_to_extract),
            data_type=data_type,
            **kwargs,
        )
        self.json_property_name = json_property_name
        self.property_to_extract = property_to_extract


class MultipleFieldsNode(Node):
    """A node that represents multiple alternative fields for a single CEL property."""
    node_type: str = Field(default="MultipleFieldsNode", const=True)
    fields: list[PropertyAccessNode] = Field(default_factory=list)
    data_type: Optional[DataType] = None


class PropertiesMappingException(Exception):
    pass


class PropertiesMapper:
    def __init__(self, properties_metadata: PropertiesMetadata):
        self.properties_metadata = properties_metadata

    def map_props_in_ast(self, abstract_node: Node) -> tuple[Node, list[PropertyMetadataInfo]]:
        involved_fields: list[PropertyMetadataInfo] = []
        mapped_ast = self.__visit_nodes(abstract_node, involved_fields)

        # dedupe by field_name
        distinct: Dict[str, PropertyMetadataInfo] = {f.field_name: f for f in involved_fields}
        return mapped_ast, list(distinct.values())

    def __visit_nodes(self, abstract_node: Node, involved_fields: list[PropertyMetadataInfo]) -> Node:
        if isinstance(abstract_node, ParenthesisNode):
            return self.__visit_nodes(abstract_node.expression, involved_fields)

        if isinstance(abstract_node, LogicalNode):
            left = self.__visit_nodes(abstract_node.left, involved_fields)
            right = self.__visit_nodes(abstract_node.right, involved_fields)

            if left is None:
                return right
            if right is None:
                return left

            return LogicalNode(left=left, operator=abstract_node.operator, right=right)

        if isinstance(abstract_node, ComparisonNode):
            return self.__visit_comparison_node(abstract_node, involved_fields)

        if isinstance(abstract_node, PropertyAccessNode):
            return self._visit_property_access_as_boolean(abstract_node, involved_fields)

        if isinstance(abstract_node, UnaryNode):
            return self.__visit_unary_node(abstract_node, involved_fields)

        if isinstance(abstract_node, ConstantNode):
            return abstract_node

        raise NotImplementedError(f"{type(abstract_node).__name__} is not supported yet")

    def __visit_unary_node(self, abstract_node: UnaryNode, involved_fields: list[PropertyMetadataInfo]) -> Node:
        # HAS(x) is essentially "x exists"
        if abstract_node.operator == UnaryNodeOperator.HAS and isinstance(abstract_node.operand, PropertyAccessNode):
            mapped, meta = self._map_property(abstract_node.operand, throw_mapping_error=False)
            involved_fields.append(meta)
            return self._exists_node(mapped)

        operand = self.__visit_nodes(abstract_node.operand, involved_fields)

        if operand is None:
            # NOT(None) -> NOT(True?) This behavior is weird. Keep your prior logic but explicit:
            return UnaryNode(operator=abstract_node.operator, operand=ConstantNode(value=True))

        return UnaryNode(operator=abstract_node.operator, operand=operand)

    def __visit_comparison_node(self, comparison_node: ComparisonNode, involved_fields: list[PropertyMetadataInfo]) -> Node:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return comparison_node

        mapped_first, meta = self._map_property(comparison_node.first_operand)
        involved_fields.append(meta)

        rebuilt = ComparisonNode(
            first_operand=mapped_first,
            operator=comparison_node.operator,
            second_operand=comparison_node.second_operand,
        )

        # If mapped_first is MultipleFieldsNode, expand comparisons across fields
        rebuilt = self._expand_multiple_fields_comparison(rebuilt)

        return self._modify_comparison_node_based_on_mapping(rebuilt, meta)

    def _visit_property_access_as_boolean(self, node: PropertyAccessNode, involved_fields: list[PropertyMetadataInfo]) -> Node:
        mapped, meta = self._map_property(node)
        involved_fields.append(meta)
        return self._truthy_node(mapped)

    # ---------- helpers for MultipleFieldsNode expansion ----------
    def _exists_node(self, node: Node) -> Node:
        # For property existence: field IS NOT NULL (and for JSON, providers can handle the path check separately if needed)
        if isinstance(node, MultipleFieldsNode):
            # any field exists
            acc: Optional[Node] = None
            for f in node.fields:
                part = ComparisonNode(first_operand=f, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value=None))
                acc = part if acc is None else LogicalNode(left=acc, operator=LogicalNodeOperator.OR, right=part)
            return acc or ConstantNode(value=False)

        return ComparisonNode(first_operand=node, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value=None))

    def _truthy_node(self, node: Node) -> Node:
        """
        Mimics JS-ish truthiness checks you were doing, but expanded for MultipleFieldsNode.
        """
        if isinstance(node, MultipleFieldsNode):
            acc: Optional[Node] = None
            for f in node.fields:
                part = self._truthy_node(f)
                acc = part if acc is None else LogicalNode(left=acc, operator=LogicalNodeOperator.OR, right=part)
            return acc or ConstantNode(value=False)

        # single field truthiness
        return LogicalNode(
            left=ComparisonNode(first_operand=node, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value=None)),
            operator=LogicalNodeOperator.AND,
            right=LogicalNode(
                left=ComparisonNode(first_operand=node, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value="0")),
                operator=LogicalNodeOperator.AND,
                right=LogicalNode(
                    left=ComparisonNode(first_operand=node, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value=False)),
                    operator=LogicalNodeOperator.AND,
                    right=ComparisonNode(first_operand=node, operator=ComparisonNodeOperator.NE, second_operand=ConstantNode(value="")),
                ),
            ),
        )

    def _expand_multiple_fields_comparison(self, comparison_node: ComparisonNode) -> ComparisonNode | Node:
        """
        If first_operand is MultipleFieldsNode, expand:
            (f1 op x) OR (f2 op x) OR ...
        """
        if not isinstance(comparison_node.first_operand, MultipleFieldsNode):
            return comparison_node

        mf = comparison_node.first_operand
        if not mf.fields:
            return ConstantNode(value=False)

        acc: Optional[Node] = None
        for f in mf.fields:
            part = ComparisonNode(first_operand=f, operator=comparison_node.operator, second_operand=comparison_node.second_operand)
            acc = part if acc is None else LogicalNode(left=acc, operator=LogicalNodeOperator.OR, right=part)

        return acc or ConstantNode(value=False)

    # ---------- mapping ----------
    def _create_property_access_node(self, mapping, data_type: Optional[DataType]) -> PropertyAccessNode:
        if isinstance(mapping, JsonFieldMapping):
            return JsonPropertyAccessNode(
                json_property_name=mapping.json_prop,
                property_to_extract=mapping.prop_in_json,
                data_type=data_type,
            )

        if isinstance(mapping, SimpleFieldMapping):
            return PropertyAccessNode(path=[mapping.map_to], data_type=data_type)

        raise NotImplementedError(f"Mapping type {type(mapping).__name__} is not supported yet")

    def _map_property(self, property_access_node: PropertyAccessNode, throw_mapping_error: bool = True) -> tuple[Node, PropertyMetadataInfo]:
        property_metadata = self.properties_metadata.get_property_metadata(property_access_node.path)

        if not property_metadata:
            joined_path = ".".join(property_access_node.path)

            if not throw_mapping_error:
                return (
                    property_access_node,
                    PropertyMetadataInfo(
                        field_name=joined_path,
                        field_mappings=[SimpleFieldMapping(joined_path)],
                        enum_values=None,
                    ),
                )

            raise PropertiesMappingException(f'Missing mapping configuration for property "{joined_path}"')

        mapped_fields: list[PropertyAccessNode] = []
        for m in property_metadata.field_mappings:
            mapped_fields.append(self._create_property_access_node(m, property_metadata.data_type))

        if len(mapped_fields) == 1:
            return mapped_fields[0], property_metadata

        return MultipleFieldsNode(fields=mapped_fields, data_type=property_metadata.data_type), property_metadata

    # ---------- enum rewrite ----------
    def _modify_comparison_node_based_on_mapping(self, comparison_node: Node, mapping: PropertyMetadataInfo) -> Node:
        if not isinstance(comparison_node, ComparisonNode):
            return comparison_node

        if not isinstance(comparison_node.second_operand, ConstantNode):
            return comparison_node

        if not mapping.enum_values:
            return comparison_node

        # Only for ordered enums. If order is not meaningful, this logic should be removed.
        if comparison_node.operator not in {
            ComparisonNodeOperator.GE,
            ComparisonNodeOperator.GT,
            ComparisonNodeOperator.LE,
            ComparisonNodeOperator.LT,
        }:
            return comparison_node

        enum_vals = mapping.enum_values
        value = comparison_node.second_operand.value

        if value not in enum_vals:
            # If value isn't in enum, your prior logic tries to "include all" or "exclude all"
            # Keep same behavior but cleanly:
            in_node = ComparisonNode(
                first_operand=comparison_node.first_operand,
                operator=ComparisonNodeOperator.IN,
                second_operand=[ConstantNode(value=item) for item in enum_vals],
            )
            if comparison_node.operator in {ComparisonNodeOperator.LT, ComparisonNodeOperator.LE}:
                return UnaryNode(operator=UnaryNodeOperator.NOT, operand=in_node)
            return in_node

        idx = enum_vals.index(value)

        if comparison_node.operator == ComparisonNodeOperator.GT:
            start = idx + 1
            if start >= len(enum_vals):
                return ConstantNode(value=False)
            allowed = enum_vals[start:]
            return ComparisonNode(
                first_operand=comparison_node.first_operand,
                operator=ComparisonNodeOperator.IN,
                second_operand=[ConstantNode(value=item) for item in allowed],
            )

        if comparison_node.operator == ComparisonNodeOperator.GE:
            allowed = enum_vals[idx:]
            return ComparisonNode(
                first_operand=comparison_node.first_operand,
                operator=ComparisonNodeOperator.IN,
                second_operand=[ConstantNode(value=item) for item in allowed],
            )

        if comparison_node.operator == ComparisonNodeOperator.LT:
            allowed = enum_vals[idx:]
            in_node = ComparisonNode(
                first_operand=comparison_node.first_operand,
                operator=ComparisonNodeOperator.IN,
                second_operand=[ConstantNode(value=item) for item in allowed],
            )
            return UnaryNode(operator=UnaryNodeOperator.NOT, operand=in_node)

        if comparison_node.operator == ComparisonNodeOperator.LE:
            start = idx + 1
            if start >= len(enum_vals):
                # everything qualifies, no filter
                return None
            allowed = enum_vals[start:]
            in_node = ComparisonNode(
                first_operand=comparison_node.first_operand,
                operator=ComparisonNodeOperator.IN,
                second_operand=[ConstantNode(value=item) for item in allowed],
            )
            return UnaryNode(operator=UnaryNodeOperator.NOT, operand=in_node)

        return comparison_node