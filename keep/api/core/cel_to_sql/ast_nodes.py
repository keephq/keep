
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

    def __init__(self, firstOperand: str, operator: str, secondOperand: str):
        self.operator = operator
        self.firstOperand = firstOperand
        self.secondOperand = secondOperand

    def __str__(self):
        return f"{self.firstOperand} {self.operator} {self.secondOperand}"

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


class PropertyAccessNode(MemberAccessNode):
    def __init__(self, member_name, value: Any):
        self.value = value
        super().__init__(member_name)
    
    def __str__(self):
        if self.value:
            return f"{self.member_name}.{self.value}"
        
        return self.member_name

class MethodAccessNode(MemberAccessNode):
    def __init__(self, member_name, args: List[str] = None):
        self.args = args
        super().__init__(member_name)

    def __str__(self):
        args = []

        for argNode in self.args:
            args.append(str(argNode))

        return f"{self.member_name}({', '.join(args)})"
