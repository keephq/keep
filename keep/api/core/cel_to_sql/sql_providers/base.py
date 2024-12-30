from keep.api.core.cel_to_sql.ast_nodes import (
    ConstantNode,
    Node,
    LogicalNode,
    ComparisonNode,
    UnaryNode,
    PropertyAccessNode,
    MethodAccessNode,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter


class BaseCelToSqlProvider:
    def convert_to_sql_str(self, cel: str, base_query: str) -> str:
        cell_ast = CelToAstConverter.convert_to_ast(cel)

        return base_query + " WHERE " + self._recursive_visit(cell_ast)

    def _recursive_visit(self, ast: Node) -> str:
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
            
        if isinstance(ast, PropertyAccessNode):
            return self._visit_property_access_node(ast)
        
        if isinstance(ast, ConstantNode):
            return self._visit_constant_node(ast.value)
        
        return ''

    def _visit_logical_and(self, left: str, right: str) -> str:
        return f"{left} AND {right}"

    def _visit_logical_or(self, left: str, right: str) -> str:
        return f"{left} OR {right}"

    def _visit_equal(self, firstOperand: str, secondOperand: str) -> str:
        return f"{firstOperand} = {secondOperand}"

    def _visit_constant_node(self, value: str) -> str:
        return f"\"{str(value)}\""
    
    def _visit_property_access_node(self, property_access_node: PropertyAccessNode) -> str:
        property_access: str = property_access_node.member_name

        if isinstance(property_access_node.value, PropertyAccessNode):
            return f"{property_access}.{self._visit_property_access_node(property_access_node.value)}"
        
        return property_access
