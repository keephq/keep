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
from datetime import datetime
import re

class BuiltQueryMetadata:
    def __init__(self, where: str, select_fields: str = None, select_json: str = None):
        self.where = where
        self.select = select_fields
        self.select_json = select_json

class BaseCelToSqlProvider:
    def __init__(self, known_fields_mapping: dict):
        super().__init__()
        self.known_fields_mapping = known_fields_mapping
        self.json_sources = {}

    def convert_to_sql_str(self, cel: str) -> BuiltQueryMetadata:
        """
        Converts a CEL (Common Expression Language) string to an SQL string.

        Args:
            cel (str): The CEL expression to convert.
            base_query (str): The base SQL query to append the converted CEL expression to.

        Returns:
            str: The resulting SQL query string with the CEL expression converted to SQL.
        """
        if not cel:
            return BuiltQueryMetadata(where="", select_fields="", select_json="")

        original_query = CelToAstConverter.convert_to_ast(cel)

        return BuiltQueryMetadata(
                where=self.__build_where_clause(original_query),
                select_fields='',
                select_json=''
            )

    def __build_where_clause(self, abstract_node: Node) -> str:
        if isinstance(abstract_node, ParenthesisNode):
            return self._visit_parentheses(
                self.__build_where_clause(abstract_node.expression)
            )

        if isinstance(abstract_node, LogicalNode):
            return self._visit_logical_node(abstract_node)

        if isinstance(abstract_node, ComparisonNode):
            return self.__modify_and_visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            return self.__modify_and_visit_member_access_node(abstract_node)

        if isinstance(abstract_node, UnaryNode):
            return self.__modify_and_visit_unary_node(abstract_node)

        if isinstance(abstract_node, ConstantNode):
            return self._visit_constant_node(abstract_node.value)

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

    def _json_extract(self, column: str, path: str) -> str:
        raise NotImplementedError("Extracting JSON is not implemented. Must be implemented in the child class.")

    def _visit_parentheses(self, node: str) -> str:
        return f"({node})"

    # region Logical Visitors
    def _visit_logical_node(self, logical_node: LogicalNode) -> str:
        left = self.__build_where_clause(logical_node.left)
        right = self.__build_where_clause(logical_node.right)

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
    def __modify_and_visit_comparison_node(self, comparison_node: ComparisonNode) -> str:
        if not isinstance(comparison_node.first_operand, PropertyAccessNode):
            return self._visit_comparison_node(comparison_node)

        result: str = None
        for mapping in self.__get_prop_mapping(
            comparison_node.first_operand.get_property_path()
        ):
            property_access_node = PropertyAccessNode(mapping, None)
            
            current_node_result = self._visit_comparison_node(ComparisonNode(
                property_access_node,
                comparison_node.operator,
                comparison_node.second_operand,
            ))
            current_node_result = self._visit_logical_and(
                left=self._visit_comparison_node(
                    ComparisonNode(
                        property_access_node,
                        ComparisonNode.NE,
                        ConstantNode(None),
                    )
                ),
                right=current_node_result
            )
            if result is None:
                result = current_node_result
                continue

            result = self._visit_logical_or(result, current_node_result)

        return result

    def _visit_comparison_node(self, comparison_node: ComparisonNode) -> str:
        first_operand = self.__build_where_clause(comparison_node.first_operand)
        second_operand = self.__build_where_clause(comparison_node.second_operand)

        if comparison_node.operator == ComparisonNode.EQ:
            result = self._visit_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.NE:
            result = self._visit_not_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.GT:
            result = self._visit_greater_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.GE:
            result = self._visit_greater_than_or_equal(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.LT:
            result = self._visit_less_than(first_operand, second_operand)
        elif comparison_node.operator == ComparisonNode.LE:
            result = self._visit_less_than_or_equal(first_operand, second_operand)
        else:
            raise NotImplementedError(
                f"{comparison_node.operator} comparison operator is not supported yet"
            )

        # if isinstance(comparison_node.second_operand, ConstantNode) and comparison_node.second_operand.value is not None:
        #     left = self._visit_not_equal(self.__build_where_clause(comparison_node.first_operand), self.__build_where_clause(ConstantNode(value=None)))
        #     right = result

        #     result = f"({self._visit_logical_and(left, right)})"

        return result

    def _cast_property(self, exp: str, to_type: type) -> str:
        if to_type == datetime:
            res = f"datetime(REPLACE(REPLACE({exp}, 'T', ' '), 'Z', ''))"
            return res
        if to_type == int:
            return exp
        if to_type == float:
            return exp
        if to_type == bool:
            return exp
            # return "TRUE" if exp == "true" else "FALSE"

        raise NotImplementedError(f"{to_type.__name__} type casting is not supported yet")

    def _visit_equal(self, first_operand: str, second_operand: str) -> str:
        return f"{first_operand} = {second_operand}"

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

    # endregion

    def _visit_constant_node(self, value: str) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, str):
            return f"'{value}'"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) or isinstance(value, int):
            return str(value)
        if isinstance(value, datetime):
            aaa = f"datetime('{value.strftime('%Y-%m-%d %H:%M:%S')}')"
            return aaa

        raise NotImplementedError(f"{type(value).__name__} constant type is not supported yet")

    # region Member Access Visitors
    def __modify_and_visit_member_access_node(self, member_access_node: MemberAccessNode) -> str:
        if (
            isinstance(member_access_node, PropertyAccessNode)
            and member_access_node.is_function_call()
        ):
            result = None
            for mapping in self.__get_prop_mapping(
                member_access_node.get_property_path()
            ):
                method_access_node = member_access_node.get_method_access_node().copy()
                property_access_node_str = self._visit_member_access_node(PropertyAccessNode(
                    mapping,
                    MethodAccessNode(
                        method_access_node.member_name,
                        method_access_node.args,
                    ),
                ))

                if result is None:
                    result = property_access_node_str
                    continue

                result = self._visit_logical_or(result, property_access_node_str)

            return result

        return self._visit_member_access_node(member_access_node)

    def _visit_member_access_node(self, member_access_node: MemberAccessNode) -> str:
        if isinstance(member_access_node, PropertyAccessNode):
            if member_access_node.is_function_call():
                method_access_node = member_access_node.get_method_access_node()
                return self._visit_method_calling(
                   self._visit_property(member_access_node.get_property_path()),
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
        # ["JSON(even_enrichment).fuck.you", "JSON(even).some.prop"]
        pattern = re.compile(r"JSON\((?P<json>[^)]+)\)\.(?P<property_path>.+)")
        match = pattern.match(property_path)

        if match:
            json_group = match.group("json")
            property_path_group = match.group("property_path")
            return self._json_extract(json_group, property_path_group)

        new_property_path = property_path
        return new_property_path

    def _visit_index_property(self, property_path: str) -> str:
        raise NotImplementedError("Index property is not supported yet")
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
    def __modify_and_visit_unary_node(self, unary_node: UnaryNode) -> str:
        result = None
        for mapping in self.__get_prop_mapping(
            unary_node.first_operand.get_property_path()
        ):
            unary_node_result = self._visit_unary_node(UnaryNode(
                unary_node.operator, PropertyAccessNode(mapping, None)
            ))
            if result is None:
                result = unary_node_result
                continue

            result = self._visit_logical_or(result, unary_node_result)

        return result

    def _visit_unary_node(self, unary_node: UnaryNode) -> str:
        if unary_node.operator == UnaryNode.NOT:
            return self._visit_unary_not(self.__build_where_clause(unary_node.operand))

        raise NotImplementedError(
            f"{unary_node.operator} unary operator is not supported yet"
        )

    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"

    # endregion
