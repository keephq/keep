from typing import Any, List

from sqlalchemy import Dialect, String

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNodeOperator,
    ConstantNode,
    DataType,
    LogicalNodeOperator,
    MemberAccessNode,
    Node,
    LogicalNode,
    ComparisonNode,
    UnaryNode,
    PropertyAccessNode,
    ParenthesisNode,
    UnaryNodeOperator,
    from_type_to_data_type,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter

from keep.api.core.cel_to_sql.properties_mapper import JsonPropertyAccessNode, MultipleFieldsNode, PropertiesMapper, PropertiesMappingException
from keep.api.core.cel_to_sql.properties_metadata import (
    JsonFieldMapping,
    PropertiesMetadata,
    PropertyMetadataInfo,
    SimpleFieldMapping,
)
from celpy import CELParseError


class CelToSqlException(Exception):
    pass


class CelToSqlResult:

    def __init__(self, sql: str, involved_fields: List[PropertyMetadataInfo]):
        self.sql = sql
        self.involved_fields = involved_fields


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
        self.properties_metadata = properties_metadata
        self.properties_mapper = PropertiesMapper(properties_metadata)

    def convert_to_sql_str(self, cel: str) -> str:
        return self.convert_to_sql_str_v2(cel).sql

    def convert_to_sql_str_v2(self, cel: str) -> CelToSqlResult:
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
            return CelToSqlResult(sql="", involved_fields=[])

        try:
            original_query = CelToAstConverter.convert_to_ast(cel)
        except CELParseError as e:
            raise CelToSqlException(f"Error parsing CEL expression: {str(e)}") from e

        try:
            with_mapped_props, involved_fields = (
                self.properties_mapper.map_props_in_ast(original_query)
            )
        except PropertiesMappingException as e:
            raise CelToSqlException(f"Error while mapping columns: {str(e)}") from e

        if not with_mapped_props:
            return CelToSqlResult(sql="", involved_fields=[])

        try:
            sql_filter = self._build_sql_filter(with_mapped_props, [])
            return CelToSqlResult(sql=sql_filter, involved_fields=involved_fields)
        except NotImplementedError as e:
            raise CelToSqlException(f"Error while converting CEL expression tree to SQL: {str(e)}") from e

    def get_order_by_expression(self, sort_options: list[tuple[str, str]]) -> str:
        sort_expressions: list[str] = []

        for sort_option in sort_options:
            sort_by, sort_dir = sort_option
            sort_dir = sort_dir.lower()
            order_by_exp = self.get_field_expression(sort_by)

            sort_expressions.append(
                f"{order_by_exp} {sort_dir == 'asc' and 'ASC' or 'DESC'}"
            )

        return ", ".join(sort_expressions)

    def get_field_expression(self, cel_field: str) -> str:
        metadata = self.properties_metadata.get_property_metadata_for_str(cel_field)
        field_expressions = []

        for field_mapping in metadata.field_mappings:
            if isinstance(field_mapping, JsonFieldMapping):
                field_expressions.append(
                    self.json_extract_as_text(
                        field_mapping.json_prop, field_mapping.prop_in_json
                    )
                )
                continue
            elif isinstance(field_mapping, SimpleFieldMapping):
                field_expressions.append(field_mapping.map_to)
                continue

            raise ValueError(f"Unsupported field mapping type: {type(field_mapping)}")

        if len(field_expressions) > 1:
            return self.coalesce(field_expressions)
        else:
            return field_expressions[0]

    def literal_proc(self, value: Any) -> str:
        if isinstance(value, str):
            return self.__literal_proc(value)

        return f"'{str(value)}'"

    def _get_order_by_field(self, cel_sort_by: str) -> str:
        return self.get_field_expression(cel_sort_by)

    def _build_sql_filter(self, abstract_node: Node, stack: list[Node]) -> str:
        stack.append(abstract_node)
        result = None

        if isinstance(abstract_node, ParenthesisNode):
            result = self._visit_parentheses(
                self._build_sql_filter(abstract_node.expression, stack)
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

    def json_extract_as_text(self, column: str, path: list[str]) -> str:
        raise NotImplementedError("Extracting JSON is not implemented. Must be implemented in the child class.")

    def coalesce(self, args):
        if len(args) == 1:
            return args[0]

        return f"COALESCE({', '.join(args)})"

    def cast(self, expression_to_cast: str, to_type: DataType, force=False) -> str:
        raise NotImplementedError("CAST is not implemented. Must be implemented in the child class.")

    def _visit_parentheses(self, node: str) -> str:
        return f"({node})"

    # region Logical Visitors
    def _visit_logical_node(self, logical_node: LogicalNode, stack: list[Node]) -> str:
        left = self._build_sql_filter(logical_node.left, stack)
        right = self._build_sql_filter(logical_node.right, stack)

        if logical_node.operator == LogicalNodeOperator.AND:
            return self._visit_logical_and(left, right)
        elif logical_node.operator == LogicalNodeOperator.OR:
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
        should_cast = comparison_node.operator not in [
            ComparisonNodeOperator.CONTAINS,
            ComparisonNodeOperator.STARTS_WITH,
            ComparisonNodeOperator.ENDS_WITH,
        ]
        first_operand_data_type = None
        second_operand_data_type = None
        force_cast = False

        if comparison_node.operator == ComparisonNodeOperator.IN:
            if (
                isinstance(comparison_node.first_operand, PropertyAccessNode)
                and comparison_node.first_operand.data_type == DataType.ARRAY
            ):
                return self._visit_in_for_array_datatype(
                    comparison_node.first_operand,
                    (
                        comparison_node.second_operand
                        if isinstance(comparison_node.second_operand, list)
                        else [comparison_node.second_operand]
                    ),
                    stack,
                )

            return self._visit_in(
                comparison_node.first_operand,
                (
                    comparison_node.second_operand
                    if isinstance(comparison_node.second_operand, list)
                    else [comparison_node.second_operand]
                ),
                stack,
            )

        if (
            comparison_node.operator == ComparisonNodeOperator.EQ
            and isinstance(comparison_node.first_operand, PropertyAccessNode)
            and comparison_node.first_operand.data_type == DataType.ARRAY
        ):
            return self._visit_equal_for_array_datatype(
                comparison_node.first_operand,
                comparison_node.second_operand,
            )

        if should_cast:
            if isinstance(comparison_node.first_operand, PropertyAccessNode):
                first_operand_data_type = comparison_node.first_operand.data_type

            if isinstance(comparison_node.first_operand, JsonPropertyAccessNode):
                first_operand_data_type = comparison_node.first_operand.data_type
                force_cast = True

            if isinstance(comparison_node.first_operand, MultipleFieldsNode):
                first_operand_data_type = comparison_node.first_operand.data_type
                force_cast = isinstance(
                    comparison_node.first_operand.fields[0], JsonPropertyAccessNode
                )

            if isinstance(comparison_node.second_operand, ConstantNode):
                second_operand_data_type = from_type_to_data_type(
                    type(comparison_node.second_operand.value)
                )
                second_operand = self._visit_constant_node(
                    comparison_node.second_operand.value,
                    first_operand_data_type,
                )

        if first_operand is None:
            first_operand = self._build_sql_filter(comparison_node.first_operand, stack)

        if second_operand is None:
            second_operand = self._build_sql_filter(
                comparison_node.second_operand, stack
            )

        if force_cast or (not first_operand_data_type and second_operand_data_type):
            first_operand = self.cast(
                first_operand,
                second_operand_data_type,
            )

        if comparison_node.operator == ComparisonNodeOperator.EQ:
            result = self._visit_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.NE:
            result = self._visit_not_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.GT:
            result = self._visit_greater_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.GE:
            result = self._visit_greater_than_or_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.LT:
            result = self._visit_less_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.LE:
            result = self._visit_less_than_or_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNodeOperator.CONTAINS:
            result = self._visit_contains_method_calling(
                first_operand, [comparison_node.second_operand]
            )
        elif comparison_node.operator == ComparisonNodeOperator.STARTS_WITH:
            result = self._visit_starts_with_method_calling(
                first_operand, [comparison_node.second_operand]
            )
        elif comparison_node.operator == ComparisonNodeOperator.ENDS_WITH:
            result = self._visit_ends_with_method_calling(
                first_operand, [comparison_node.second_operand]
            )
        else:
            raise NotImplementedError(
                f"{comparison_node.operator} comparison operator is not supported yet"
            )

        return result

    def _visit_equal(self, first_operand: str, second_operand: str) -> str:
        if second_operand == "NULL":
            return f"{first_operand} IS NULL"

        return f"{first_operand} = {second_operand}"

    def _visit_equal_for_array_datatype(
        self, first_operand: Node, second_operand: Node
    ) -> str:
        raise NotImplementedError(
            "Array datatype comparison is not implemented. Must be implemented in the child class."
        )

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
        constant_value_type = type(array[0].value)
        cast_to = None

        if not all(isinstance(item.value, constant_value_type) for item in array):
            cast_to = DataType.STRING

        if isinstance(first_operand, JsonPropertyAccessNode):
            first_operand_str = self._visit_property_access_node(first_operand, stack)
            if first_operand.data_type:
                first_operand_str = self.cast(
                    first_operand_str, first_operand.data_type
                )
        elif isinstance(first_operand, PropertyAccessNode):
            first_operand_str = self._visit_property_access_node(first_operand, stack)
            if cast_to:
                first_operand_str = self.cast(first_operand_str, cast_to)
        elif isinstance(first_operand, MultipleFieldsNode):
            first_operand_str = self._visit_multiple_fields_node(
                first_operand, None, stack
            )
            if next(
                (
                    item
                    for item in iter(first_operand.fields)
                    if isinstance(item, JsonPropertyAccessNode)
                ),
                False,
            ):
                if first_operand.data_type:
                    first_operand_str = self.cast(
                        first_operand_str, first_operand.data_type
                    )
                first_operand_str = first_operand_str

        else:
            first_operand_str = self._build_sql_filter(first_operand, stack)

        constant_nodes_without_none = []
        is_none_found = False

        for item in array:
            if isinstance(item, ConstantNode):
                if item.value is None:
                    is_none_found = True
                    continue
                constant_nodes_without_none.append(item)

        or_queries = []

        if len(constant_nodes_without_none) > 0:
            or_queries.append(
                f"{first_operand_str} in ({ ', '.join([self._visit_constant_node(c.value, self._get_data_type_to_convert(first_operand)) for c in constant_nodes_without_none])})"
            )

        if is_none_found:
            or_queries.append(self._visit_equal(first_operand_str, "NULL"))

        if len(or_queries) == 0:
            return self._visit_constant_node(False)

        final_query = or_queries[0]

        for query in or_queries[1:]:
            final_query = self._visit_logical_or(final_query, query)

        return final_query

    def _visit_in_for_array_datatype(
        self, first_operand: Node, array: list[ConstantNode], stack: list[Node]
    ) -> str:
        raise NotImplementedError(
            "Array datatype IN operator is not implemented. Must be implemented in the child class."
        )

    def _visit_contains_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError(
            "'contains' method must be implemented in the child class"
        )

    def _visit_starts_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError(
            "'startsWith' method call must be implemented in the child class"
        )

    def _visit_ends_with_method_calling(
        self, property_path: str, method_args: List[ConstantNode]
    ) -> str:
        raise NotImplementedError(
            "'endsWith' method call must be implemented in the child class"
        )

    # endregion

    def _visit_constant_node(
        self, value: Any, expected_data_type: DataType = None
    ) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, str):
            return self.literal_proc(value)
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) or isinstance(value, int):
            return str(value)

        raise NotImplementedError(f"{type(value).__name__} constant type is not supported yet. Consider implementing this support in child class.")

    def _get_data_type_to_convert(self, node: Node) -> DataType:
        """
        Extracts data type from node.
        The data type will be used to convert the value of constant node into the expected type (SQL type).
        """
        if isinstance(node, PropertyAccessNode):
            return node.data_type

        if isinstance(node, MultipleFieldsNode):
            return node.data_type

        if isinstance(node, ComparisonNode):
            return self._get_data_type_to_convert(node.first_operand)

        raise NotImplementedError(
            f"Cannot find data type to convert for {type(node).__name__} node"
        )

    # region Member Access Visitors
    def _visit_multiple_fields_node(
        self, multiple_fields_node: MultipleFieldsNode, cast_to: DataType, stack
    ) -> str:
        coalesce_args = []

        for item in multiple_fields_node.fields:
            arg = self._visit_property_access_node(item, stack)
            if isinstance(item, JsonPropertyAccessNode) and cast_to:
                arg = self.cast(arg, cast_to)
            coalesce_args.append(arg)

        if len(coalesce_args) == 1:
            return coalesce_args[0]

        return self.coalesce(coalesce_args)

    def _visit_member_access_node(self, member_access_node: MemberAccessNode, stack) -> str:
        if isinstance(member_access_node, PropertyAccessNode):
            return self._visit_property_access_node(member_access_node, stack)

        raise NotImplementedError(
            f"{type(member_access_node).__name__} member access node is not supported yet"
        )

    def _visit_property_access_node(self, property_access_node: PropertyAccessNode, stack: list[Node]) -> str:
        if (isinstance(property_access_node, JsonPropertyAccessNode)):
            return self.json_extract_as_text(property_access_node.json_property_name, property_access_node.property_to_extract)

        return ".".join([f"{item}" for item in property_access_node.path])

    def _visit_index_property(self, property_path: str) -> str:
        raise NotImplementedError("Index property is not supported yet")
    # endregion

    # region Unary Visitors
    def _visit_unary_node(self, unary_node: UnaryNode, stack: list[Node]) -> str:
        if unary_node.operator == UnaryNodeOperator.NOT:
            return self._visit_unary_not(
                self._build_sql_filter(unary_node.operand, stack)
            )

        raise NotImplementedError(
            f"{unary_node.operator} unary operator is not supported yet"
        )

    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"

    # endregion
