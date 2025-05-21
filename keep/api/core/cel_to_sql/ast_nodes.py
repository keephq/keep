import datetime
from types import NoneType
from typing import Any, List, Optional

from enum import Enum

from pydantic import BaseModel, Field


class Node(BaseModel):
    """
    A base class representing a node in an abstract syntax tree (AST).

    This class serves as a parent class for various types of nodes that can
    appear in an AST. It does not implement any specific functionality but
    provides a common interface for all AST nodes.
    """
    def __init__(self, **data):
        super().__init__(**data)

    node_type: str = Field(default=None)

    @property
    def __str(self):
        """
        Returns string representation of Node. The property used for debugging
        """
        return str(self)


class ConstantNode(Node):
    """
    A node representing a constant value in CEL abstract syntax tree.
    Example: 1, 'text', true

    Attributes:
        value (Any): The constant value represented by this node.

    Methods:
        __str__(): Returns the string representation of the constant value.
    """
    node_type: str = Field(default="ConstantNode", const=True)
    value: Any = Field()

    def __str__(self):
        if self.value is None:
            return "null"
        if isinstance(self.value, str):
            return f"'{self.value}'"
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        if isinstance(self.value, (int, float)):
            return str(self.value)
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
    node_type: str = Field(default="ParenthesisNode", const=True)
    expression: Node = Field()

    def __str__(self):
        return f"({self.expression})"


class LogicalNodeOperator(Enum):
    AND = "&&"
    OR = "||"


class LogicalNode(Node):
    """
    Represents a logical operation node in CEL abstract syntax tree (AST).
    Examples:
        alert.status == 'open' && alert.severity == 'high'
        alert.status == 'open' || alert.severity == 'high'
    Attributes:
        left (Any): The left operand of the logical operation.
        operator (str): The logical operator ('&&' for AND, '||' for OR).
        right (Any): The right operand of the logical operation.
    Methods:
        __init__(left: Any, operator: str, right: Any):
            Initializes a LogicalNode with the given left operand, operator, and right operand.
        __str__() -> str:
            Returns a string representation of the logical operation in the format "left operator right".
    """
    node_type: str = Field(default="LogicalNode", const=True)
    left: Node = Field()
    operator: LogicalNodeOperator = Field()
    right: Node = Field()

    def __str__(self):
        return f"{self.left} {self.operator.value} {self.right }"

class ComparisonNodeOperator(Enum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "=="
    NE = "!="
    IN = "in"
    CONTAINS = "contains"
    STARTS_WITH = "startsWith"
    ENDS_WITH = "endsWith"


class ComparisonNode(Node):
    """
    A class representing a comparison operation in CEL abstract syntax tree (AST).
    Examples:
        alert.severity == 'high'
        alert.count > 10
        alert.status != 'closed'

    Args:
        first_operand (Node): The left-hand side operand of the comparison.
        operator (str): The comparison operator.
        second_operand (Node): The right-hand side operand of the comparison.

    Methods:
        __str__(): Returns a string representation of the comparison operation.
    """
    node_type: str = Field(default="ComparisonNode", const=True)
    first_operand: Optional[Node] = Field()
    operator: ComparisonNodeOperator = Field()
    second_operand: Optional[Node | Any] = Field()

    def __str__(self):
        operand_value = None

        if self.operator == ComparisonNodeOperator.IN:
            operand_value = (
                f"[{', '.join([str(item) for item in self.second_operand])}]"
            )
        elif self.operator in [
            ComparisonNodeOperator.CONTAINS,
            ComparisonNodeOperator.STARTS_WITH,
            ComparisonNodeOperator.ENDS_WITH,
        ]:
            return f"{self.first_operand}.{self.operator.value}({self.second_operand})"
        else:
            operand_value = str(self.second_operand)

        return f"{self.first_operand} {self.operator.value} {operand_value}"


class UnaryNodeOperator(Enum):
    NOT = "!"
    NEG = "-"


class UnaryNode(Node):
    """
    Represents a unary operation node in CEL abstract syntax tree (AST).
    Examples:
        !alert.active
        -alert.threshold
    Attributes:
        operator (str): The operator for the unary operation.
        operand (Any): The operand for the unary operation.
    Methods:
        __init__(operator: str, operand: Any):
            Initializes a UnaryNode with the given operator and operand.
        __str__() -> str:
            Returns a string representation of the unary operation.
    """
    node_type: str = Field(default="UnaryNode", const=True)
    operator: UnaryNodeOperator = Field()
    operand: Optional[Node] = Field()

    def __str__(self):
        return f"{self.operator.value}{self.operand}"


class DataType(Enum):
    """
    An enumeration representing various data types.

    Attributes:
        STRING (str): Represents a string data type.
        UUID (str): Represents a universally unique identifier (UUID) data type.
        INTEGER (str): Represents an integer data type.
        FLOAT (str): Represents a floating-point number data type.
        DATETIME (str): Represents a datetime data type.
        BOOLEAN (str): Represents a boolean data type.
        OBJECT (str): Represents an object data type.
        ARRAY (str): Represents an array data type.
    """

    STRING = "string"
    UUID = "uuid"
    INTEGER = "integer"
    FLOAT = "float"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


def from_type_to_data_type(_type: type) -> DataType:
    if _type is str:
        return DataType.STRING
    elif _type is int:
        return DataType.INTEGER
    elif _type is float:
        return DataType.FLOAT
    elif _type is bool:
        return DataType.BOOLEAN
    elif _type is NoneType:
        return DataType.NULL
    elif _type is dict:
        return DataType.OBJECT
    elif _type is list:
        return DataType.ARRAY
    elif _type is datetime.datetime:
        return DataType.DATETIME

    raise ValueError(
        f"There is no DataType corresponding to the provided type: {_type}"
    )


class PropertyAccessNode(Node):
    """
    Represents a node in CEL abstract syntax tree (AST) that accesses a property of an object.
    Examples:
        alert.name
        alert.status
    Attributes:
        path (str): The property path being accessed.
        value (Any): The value associated with the member access, which can be another node.
    Methods:
        __init__(member_name, value: Any):
            Initializes the PropertyAccessNode with the given member name and value.
        __str__() -> str:
            Returns a string representation of the PropertyAccessNode.
    """
    node_type: str = Field(default="PropertyAccessNode", const=True)
    path: list[str] = Field(default=None)
    data_type: DataType = Field(default=None)

    def __str__(self):
        return ".".join(self.path)


class CoalesceNode(Node):
    """
    Represents a Coalesce node in an abstract syntax tree (AST).

    A CoalesceNode is used to represent a coalesce operation, which evaluates
    a list of properties and returns the first non-null value.

    Attributes:
        properties (List[PropertyAccessNode]): A list of PropertyAccessNode
            objects representing the properties to be evaluated in the coalesce
            operation.

    Methods:
        __str__(): Returns a string representation of the coalesce operation
            in the format "coalesce(prop1, prop2, ...)".
    """

    node_type: str = Field(default="CoalesceNode", const=True)
    properties: list[PropertyAccessNode] = Field(default=None)

    def __str__(self):
        return f"coalesce({', '.join([str(prop) for prop in self.properties])})"
