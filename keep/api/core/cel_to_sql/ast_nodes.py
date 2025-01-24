
from typing import Any, List


class Node:
    """
    A base class representing a node in an abstract syntax tree (AST).

    This class serves as a parent class for various types of nodes that can
    appear in an AST. It does not implement any specific functionality but
    provides a common interface for all AST nodes.
    """

class ConstantNode(Node):
    """
    A node representing a constant value in CEL abstract syntax tree.
    Example: 1, 'text', true

    Attributes:
        value (Any): The constant value represented by this node.

    Methods:
        __str__(): Returns the string representation of the constant value.
    """
    def __init__(self, value: Any):
        self.value = value

    def __str__(self):
        return self.value

class ParenthesisNode(Node):
    """
    A node representing a parenthesis expression in CEL abstract syntax tree (AST).
    Example: (alert.status == 'open')
    Attributes:
        expression (Any): The expression contained within the parentheses.

    Methods:
        __str__(): Returns a string representation of the parenthesis node.
    """
    def __init__(self, expression: Any):
        self.expression = expression

    def __str__(self):
        return f"({self.expression})"

class LogicalNode(Node):
    """
    Represents a logical operation node in CEL abstract syntax tree (AST).
    Examples: 
        alert.status == 'open' && alert.severity == 'high'
        alert.status == 'open' || alert.severity == 'high'
    Attributes:
        AND (str): The logical AND operator.
        OR (str): The logical OR operator.
        left (Any): The left operand of the logical operation.
        operator (str): The logical operator ('&&' for AND, '||' for OR).
        right (Any): The right operand of the logical operation.
    Methods:
        __init__(left: Any, operator: str, right: Any):
            Initializes a LogicalNode with the given left operand, operator, and right operand.
        __str__() -> str:
            Returns a string representation of the logical operation in the format "left operator right".
    """
    AND = '&&'
    OR = '||'

    def __init__(self, left: Any, operator: str, right: Any):
        self.left = left
        self.operator = operator
        self.right = right
    
    def __str__(self):
        return f"{self.left} {self.operator} {self.right}"

class ComparisonNode(Node):
    """
    A class representing a comparison operation in CEL abstract syntax tree (AST).
    Examples:
        alert.severity == 'high'
        alert.count > 10
        alert.status != 'closed'
    Attributes:
        LT (str): Less than operator ('<').
        LE (str): Less than or equal to operator ('<=').
        GT (str): Greater than operator ('>').
        GE (str): Greater than or equal to operator ('>=').
        EQ (str): Equal to operator ('==').
        NE (str): Not equal to operator ('!==').
        IN (str): In operator ('in').

    Args:
        first_operand (Node): The left-hand side operand of the comparison.
        operator (str): The comparison operator.
        second_operand (Node): The right-hand side operand of the comparison.

    Methods:
        __str__(): Returns a string representation of the comparison operation.
    """
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
    """
    Represents a unary operation node in CEL abstract syntax tree (AST).
    Examples:
        !alert.active
        -alert.threshold
    Attributes:
        NOT (str): The logical NOT operator.
        NEG (str): The negation operator.
        operator (str): The operator for the unary operation.
        operand (Any): The operand for the unary operation.
    Methods:
        __init__(operator: str, operand: Any):
            Initializes a UnaryNode with the given operator and operand.
        __str__() -> str:
            Returns a string representation of the unary operation.
    """
    NOT = '!'
    NEG = '-'

    def __init__(self, operator: str, operand: Any):
        self.operator = operator
        self.operand = operand
    
    def __str__(self):
        return f"{self.operator}{self.operand}"
    
class MemberAccessNode(Node):
    """
    A node representing member access in CEL abstract syntax tree (AST).
    Attributes:
        member_name (str): The name of the member being accessed.
    Methods:
        __str__(): Returns the member name as a string.
    """
    def __init__(self, member_name: str):
        self.member_name = member_name
    
    def __str__(self):
        return self.member_name

class MethodAccessNode(MemberAccessNode):
    """
    Represents a method access node in CEL abstract syntax tree (AST).
    Examples:
        alert.name.contains('error')
        alert.name.startsWith('sys')
        alert.name.endsWith('log')
    Inherits from:
        MemberAccessNode

    Attributes:
        member_name (str): The name of the member being accessed.
        args (List[str], optional): A list of arguments for the method. Defaults to None.

    Methods:
        copy() -> MethodAccessNode:
            Creates a copy of the current MethodAccessNode instance.
        
        __str__() -> str:
            Returns a string representation of the method access node in the format:
            "member_name(arg1, arg2, ...)".
    """
    def __init__(self, member_name, args: List[str] = None):
        self.args = args
        super().__init__(member_name)

    def copy(self):
        return MethodAccessNode(self.member_name, self.args.copy() if self.args else None)

    def __str__(self):
        args = []

        for arg_node in self.args:
            args.append(str(arg_node))

        return f"{self.member_name}({', '.join(args)})"

class PropertyAccessNode(MemberAccessNode):
    """
    Represents a node in CEL abstract syntax tree (AST) that accesses a property of an object.
    Examples:
        alert.name
        alert.status
    Attributes:
        member_name (str): The name of the member being accessed.
        value (Any): The value associated with the member access, which can be another node.
    Methods:
        __init__(member_name, value: Any):
            Initializes the PropertyAccessNode with the given member name and value.
        is_function_call() -> bool:
            Determines if the member access represents a function call.
        get_property_path() -> str:
            Constructs and returns the property path as a string.
        get_method_access_node() -> MethodAccessNode:
            Retrieves the MethodAccessNode if the value represents a method access.
        __str__() -> str:
            Returns a string representation of the PropertyAccessNode.
    """

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
    """
    Represents an index access node in CEL abstract syntax tree (AST).
    This node is used to represent access to a property or method via an index.
    Examples:
        alert['name']
        alert['status']
    Attributes:
        member_name (str): The name of the member being accessed.
        value (Any): The value associated with the member, which can be another node.
    Methods:
        get_property_path() -> str:
            Returns the property path as a string, including the member name and any nested method access.
        __str__() -> str:
            Returns a string representation of the index access node.
    """
    def __init__(self, member_name: str, value: Any):
        super().__init__(member_name, value)

    def get_property_path(self) -> str:
        if isinstance(self.value, MethodAccessNode):
            return f"[{str(self.member_name)}].{self.value.get_property_path()}"
        
        return f"[{str(self.member_name)}]"

    def __str__(self):
        return f"[{self.member_name}]"
