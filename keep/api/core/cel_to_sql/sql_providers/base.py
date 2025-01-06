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


class SqlField:
    def __init__(self, field_name: str, field_type: str, take_from_json_in=None):
        self.field_name = field_name
        self.field_type = field_type
        self.take_from_json_in = take_from_json_in

    def __str__(self):
        return f"{self.field_name} {self.field_type}"

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

        cell_ast = CelToAstConverter.convert_to_ast(cel)

        property_nodes = self._recursive_get_property_nodes(cell_ast)

        return BuiltQueryMetadata(
                where=self.__build_where_clause(cell_ast),
                select_fields=self.__create_select_fields_clause(property_nodes),
                select_json= self.__create_json_sources_clause(property_nodes)
            )
    
    def __create_json_sources_clause(self, property_nodes: List[PropertyAccessNode]):
        select_json: dict[str, List[str]] = {}

        for property_node in property_nodes:
            if property_node.get_property_path() not in self.known_fields_mapping:
                if "*" in self.known_fields_mapping:
                    generic_field = self.known_fields_mapping["*"]
                    take_from = generic_field.get("take_from")
                    take_from_key = "_".join(take_from)
                    select_json[take_from_key] = take_from
                    
        select_json_entries = []
        for key, value in select_json.items():
            select_json_entries.append(f"{self._json_merge(value)} AS {key}")
        
        return ", ".join(select_json_entries)
    
    def __create_select_fields_clause(self, property_nodes: List[PropertyAccessNode]):
        select_fields = []

        for property_node in property_nodes:
            if property_node.get_property_path() not in self.known_fields_mapping:
                if "*" in self.known_fields_mapping:
                    generic_field = self.known_fields_mapping["*"]
                    take_from = generic_field.get("take_from")
                    take_from_key = "_".join(take_from)
                    new_prop_name = "_".join(take_from + property_node.get_property_path().replace('[', '_').replace(']', '_').split("."))
                    select_fields.append(f"{self._json_extract(take_from_key, property_node.get_property_path())} AS {new_prop_name}")
        
        return ", ".join(select_fields)

    def __build_where_clause(self, abstract_node: Node) -> str:
        if isinstance(abstract_node, ParenthesisNode):
            return self._visit_parentheses(
                self.__build_where_clause(abstract_node.expression)
            )

        if isinstance(abstract_node, LogicalNode):
            return self._visit_logical_node(abstract_node)

        if isinstance(abstract_node, ComparisonNode):
            return self._visit_comparison_node(abstract_node)

        if isinstance(abstract_node, MemberAccessNode):
            return self._visit_member_access_node(abstract_node)

        if isinstance(abstract_node, UnaryNode):
            return self._visit_unary_node(abstract_node)

        if isinstance(abstract_node, ConstantNode):
            return self._visit_constant_node(abstract_node.value)

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

    def _json_merge(self, columns: List[str]) -> str:
        raise NotImplementedError("Merging JSON is not implemented. Must be implemented in the child class.")
    
    def _json_extract(self, column: str, path: str) -> str:
        raise NotImplementedError("Extracting JSON is not implemented. Must be implemented in the child class.")

    def _recursive_get_property_nodes(self, abstract_node: Node) -> List[PropertyAccessNode]:
        if isinstance(abstract_node, PropertyAccessNode):
            return [abstract_node]

        if isinstance(abstract_node, ParenthesisNode):
            return self._recursive_get_property_nodes(abstract_node.expression)

        if isinstance(abstract_node, LogicalNode):
            return self._recursive_get_property_nodes(abstract_node.left) + self._recursive_get_property_nodes(abstract_node.right)

        if isinstance(abstract_node, ComparisonNode):
            return self._recursive_get_property_nodes(abstract_node.first_operand) + self._recursive_get_property_nodes(abstract_node.second_operand)

        if isinstance(abstract_node, MemberAccessNode):
            return self._recursive_get_property_nodes(abstract_node.get_property_path())

        if isinstance(abstract_node, UnaryNode):
            return self._recursive_get_property_nodes(abstract_node.operand)

        if isinstance(abstract_node, ConstantNode):
            return []

        raise NotImplementedError(
            f"{type(abstract_node).__name__} node type is not supported yet"
        )

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
    def _visit_comparison_node(self, comparison_node: ComparisonNode) -> str:
        

        first_operand = self.__build_where_clause(comparison_node.first_operand)
        second_operand = self.__build_where_clause(comparison_node.second_operand)

        if isinstance(comparison_node.first_operand, PropertyAccessNode) and isinstance(comparison_node.second_operand, ConstantNode):
            if not isinstance(comparison_node.second_operand.value, str):
                first_operand = self._cast_property(first_operand, type(comparison_node.second_operand.value))
        result: str = ""

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

        if isinstance(comparison_node.second_operand, ConstantNode) and comparison_node.second_operand.value is not None:
            left = self._visit_not_equal(self.__build_where_clause(comparison_node.first_operand), self.__build_where_clause(ConstantNode(value=None)))
            right = result

            aa = f"({self._visit_logical_and(left, right)})"

            return aa

        return result
    
    def _cast_property(self, exp: str, to_type: type) -> str:
        if to_type == datetime:
            res = f"datetime(REPLACE(REPLACE({exp}, 'T', ' '), 'Z', ''))"
            return res
        if to_type == int:
            return exp
        if to_type == float:
            return exp
        
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
        new_property_path = property_path

        if property_path in self.known_fields_mapping:
            new_property_path = self.known_fields_mapping[property_path].get("field")
        elif self.known_fields_mapping.get("*"):
            generic_field = self.known_fields_mapping["*"]
            take_from = generic_field.get("take_from")
            new_property_path = "_".join(take_from + property_path.replace('[', '_').replace(']', '_').split("."))

        # if ('lastReceived' == property_path):
        #     new_property_path = f"datetime(REPLACE(REPLACE({new_property_path}, 'T', ' '), 'Z', ''))"
        #     # new_property_path = f"datetime({new_property_path})"

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
    def _visit_unary_node(self, unary_node: UnaryNode) -> str:
        if unary_node.operator == UnaryNode.NOT:
            return self._visit_unary_not(self.__build_where_clause(unary_node.operand))

        raise NotImplementedError(
            f"{unary_node.operator} unary operator is not supported yet"
        )

    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"

    # endregion
