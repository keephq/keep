
from typing import Any, List


class Node:
    pass

class ConstantNode(Node):
    def __init__(self, value: Any):
        self.value = value

    def __str__(self):
        return self.value

class ParenthesisNode(Node):
    def __init__(self, expression: Any):
        self.expression = expression

    def __str__(self):
        return f"({self.expression})"

class LogicalNode(Node):
    AND = '&&'
    OR = '||'

    def __init__(self, left: Any, operator: str, right: Any):
        self.left = left
        self.operator = operator
        self.right = right
    
    def __str__(self):
        return f"{self.left} {self.operator} {self.right}"

class ComparisonNode(Node):
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='
    EQ = '=='
    NE = '!=='
    IN = 'in'

    def __init__(self, first_operand: Node, operator: str, second_operand: Node):
        self.operator = operator
        self.first_operand = first_operand
        self.second_operand = second_operand

    def __str__(self):
        return f"{self.first_operand} {self.operator} {self.second_operand}"

class UnaryNode(Node):
    NOT = '!'
    NEG = '-'

    def __init__(self, operator: str, operand: Any):
        self.operator = operator
        self.operand = operand
    
    def __str__(self):
        return f"{self.operator}{self.operand}"
    
class MemberAccessNode(Node):
    def __init__(self, member_name: str):
        self.member_name = member_name
    
    def __str__(self):
        return self.member_name

class MethodAccessNode(MemberAccessNode):
    def __init__(self, member_name, args: List[str] = None):
        self.args = args
        super().__init__(member_name)

    def __str__(self):
        args = []

        for arg_node in self.args:
            args.append(str(arg_node))

        return f"{self.member_name}({', '.join(args)})"

class PropertyAccessNode(MemberAccessNode):
    def __init__(self, member_name, value: Any):
        self.value = value
        super().__init__(member_name)

    def is_function_call(self) -> bool:
        member_access_node = self.get_method_access_node()

        return member_access_node is not None
    
    def get_property_path(self) -> str:
        if isinstance(self.value, IndexAccessNode):
            return f"{self.member_name}{self.value.get_property_path()}"

        if isinstance(self.value, PropertyAccessNode):
            return f"{self.member_name}.{self.value.get_property_path()}"
        
        return self.member_name
    
    def get_method_access_node(self) -> MethodAccessNode:
        if isinstance(self.value, MethodAccessNode):
            return self.value

        if isinstance(self.value, PropertyAccessNode):
            return self.value.get_method_access_node()
        
        return None
    
    def __str__(self):
        if self.value:
            return f"{self.member_name}.{self.value}"
        
        return self.member_name
    
class IndexAccessNode(PropertyAccessNode):
    def __init__(self, member_name: str, value: Any):
        super().__init__(member_name, value)

    def get_property_path(self) -> str:
        if isinstance(self.value, MethodAccessNode):
            return f"[{str(self.member_name)}].{self.value.get_property_path()}"
        
        return f"[{str(self.member_name)}]"

    def __str__(self):
        return f"[{self.member_name}]"
