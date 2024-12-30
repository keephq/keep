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
    ParenthesisNode
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
                     
class SqlField:
    def __init__(self, field_name: str, field_type: str, take_from_json_in=None):
        self.field_name = field_name
        self.field_type = field_type
        self.take_from_json_in = take_from_json_in

    def __str__(self):
        return f"{self.field_name} {self.field_type}"

class BaseCelToSqlProvider:
    # def __init__(self, sql_fields: List[SqlField]):
    #     self._sql_fields_dict = {field.field_name: field for field in sql_fields}

    def convert_to_sql_str(self, cel: str, base_query: str) -> str:
        cell_ast = CelToAstConverter.convert_to_ast(cel)

        return base_query + " WHERE " + self._recursive_visit(cell_ast)

    def _recursive_visit(self, ast: Node) -> str:
        if isinstance(ast, ParenthesisNode):
            return self._visit_parentheses(self._recursive_visit(ast.expression))
        if isinstance(ast, LogicalNode):
            left = self._recursive_visit(ast.left)
            right = self._recursive_visit(ast.right)

            if ast.operator == LogicalNode.AND:
                return self._visit_logical_and(left, right)
            elif ast.operator == LogicalNode.OR:
                return self._visit_logical_or(left, right)

        if isinstance(ast, ComparisonNode):
            firstOperand = self._recursive_visit(ast.firstOperand)
            secondOperand = self._recursive_visit(ast.secondOperand)

            if ast.operator == ComparisonNode.EQ:
                return self._visit_equal(firstOperand, secondOperand)
            elif ast.operator == ComparisonNode.NE:
                return self._visit_not_equal(firstOperand, secondOperand)
            
            raise NotImplementedError(f"{ast.operator} comparison operator is not supported yet")
            
        if isinstance(ast, MemberAccessNode):
            if isinstance(ast, PropertyAccessNode):
                if ast.is_function_call():
                    method_access_node = ast.get_method_access_node()
                    return self._visit_method_calling(ast.get_property_path(), method_access_node.member_name, method_access_node.args)
                
                return self._visit_property(ast.get_property_path())

            if isinstance(ast, MethodAccessNode):
                return self._visit_method_calling(None, ast.member_name, ast.args)      
        
        if isinstance(ast, UnaryNode):
            if ast.operator == UnaryNode.NOT:
                return self._visit_unary_not(self._recursive_visit(ast.operand))
            
            raise NotImplementedError(f"{ast.operator} unary operator is not supported yet")

        if isinstance(ast, ConstantNode):
            return self._visit_constant_node(ast.value)
        
        raise NotImplementedError(f"{type(ast).__name__} node type is not supported yet")
    
    def _visit_parentheses(self, node: str) -> str:
        return f"({node})"

    #region Logical Visitors
    def _visit_logical_and(self, left: str, right: str) -> str:
        return f"{left} AND {right}"

    def _visit_logical_or(self, left: str, right: str) -> str:
        return f"{left} OR {right}"
    #endregion

    #region Comparison Visitors
    def _visit_equal(self, firstOperand: str, secondOperand: str) -> str:
        return f"{firstOperand} = {secondOperand}"
    
    def _visit_not_equal(self, firstOperand: str, secondOperand: str) -> str:
        return f"{firstOperand} != {secondOperand}"
    #endregion

    def _visit_constant_node(self, value: str) -> str:
        return f"\"{str(value)}\""
    
    def _visit_property(self, property_path: str) -> str:
        return property_path
    
    #region Method Calling Visitors
    def _visit_method_calling(self, property_path: str, method_name: str, method_args: List[str]) -> str:
        if method_name == 'contains':
            return self._visit_contains_method_calling(property_path, method_args)

        if method_name == 'startsWith':
            return self._visit_startwith_method_calling(property_path, method_args)
        
        if method_name == 'endsWith':
            return self._visit_endswith_method_calling(property_path, method_args)

        raise NotImplementedError(f"'{method_name}' method is not supported")
    
    def _visit_contains_method_calling(self, property_path: str, method_args: List[str]) -> str:
        raise NotImplementedError("'contains' method call is not supported")
    
    def _visit_startwith_method_calling(self, property_path: str, method_args: List[str]) -> str:
        raise NotImplementedError("'startswith' method call is not supported")
    
    def _visit_endswith_method_calling(self, property_path: str, method_args: List[str]) -> str:
        raise NotImplementedError("'endswith' method call is not supported")
    #endregion
    
    def _visit_unary_not(self, operand: str) -> str:
        return f"NOT ({operand})"