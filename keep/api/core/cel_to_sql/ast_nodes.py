import datetime
from enum import Enum
from typing import Any, List, Optional, Union
from types import NoneType

from pydantic import BaseModel, Field


# ----------------------------
# Base Node
# ----------------------------

class Node(BaseModel):
    """
    Base class for all AST nodes.
    """
    node_type: str = Field(default="Node")


# ----------------------------
# Constants & Parentheses
# ----------------------------

class ConstantNode(Node):
    node_type: str = Field(default="ConstantNode")
    value: Any = Field()

    def __str__(self) -> str:
        return str(self.value)


class ParenthesisNode(Node):
    node_type: str = Field(default="ParenthesisNode")
    expression: Node = Field()

    def __str__(self) -> str:
        return f"({self.expression})"


# ----------------------------
# Logical
# ----------------------------

class LogicalNodeOperator(str, Enum):
    AND = "&&"
    OR = "||"


class LogicalNode(Node):
    node_type: str = Field(default="LogicalNode")
    left: Node = Field()
    operator: LogicalNodeOperator = Field()
    right: Node = Field()

    def __str__(self) -> str:
        return f"{self.left} {self.operator.value} {self.right}"


# ----------------------------
# Comparison
# ----------------------------

class ComparisonNodeOperator(str, Enum):
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


SecondOperand = Union[Node, List["ConstantNode"], None]


class ComparisonNode(Node):
    node_type: str = Field(default="ComparisonNode")
    first_operand: Optional[Node] = Field(default=None)
    operator: ComparisonNodeOperator = Field()
    second_operand: SecondOperand = Field(default=None)

    def __str__(self) -> str:
        return f"{self.first_operand} {self.operator.value} {self.second_operand}"


# ----------------------------
# Unary
# ----------------------------

class UnaryNodeOperator(str, Enum):
    NOT = "!"
    NEG = "-"
    HAS = "has"


class UnaryNode(Node):
    node_type: str = Field(default="UnaryNode")
    operator: UnaryNodeOperator = Field()
    operand: Optional[Node] = Field(default=None)

    def __str__(self) -> str:
        if self.operator == UnaryNodeOperator.HAS:
            return f"has({self.operand})"
        return f"{self.operator.value}{self.operand}"


# ----------------------------
# Access / Member / Methods
# ----------------------------

class MemberAccessNode(Node):
    """
    Legacy compatibility node. If you're removing this later, fine,
    but it must be structurally valid until then.
    """
    node_type: str = Field(default="MemberAccessNode")
    member_name: str = Field()
    value: Optional[Node] = Field(default=None)

    def __str__(self) -> str:
        return self.member_name if self.value is None else f"{self.member_name}.{self.value}"


class MethodAccessNode(MemberAccessNode):
    node_type: str = Field(default="MethodAccessNode")
    args: List[ConstantNode] = Field(default_factory=list)

    def copy(self) -> "MethodAccessNode":
        return MethodAccessNode(
            member_name=self.member_name,
            value=self.value,
            args=self.args.copy(),
        )

    def __str__(self) -> str:
        rendered_args = ", ".join(str(a) for a in self.args)
        return f"{self.member_name}({rendered_args})"


# ----------------------------
# Data types
# ----------------------------

class DataType(str, Enum):
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
    # bool must come before int (bool is a subclass of int)
    if _type is bool:
        return DataType.BOOLEAN
    if _type is str:
        return DataType.STRING
    if _type is int:
        return DataType.INTEGER
    if _type is float:
        return DataType.FLOAT
    if _type is NoneType:
        return DataType.NULL
    if _type is dict:
        return DataType.OBJECT
    if _type is list:
        return DataType.ARRAY
    if _type is datetime.datetime:
        return DataType.DATETIME

    raise ValueError(f"No DataType mapping for: {_type}")


class PropertyAccessNode(MemberAccessNode):
    """
    Prefer rendering from path if you're using it for SQL generation.
    Keep member_name/value for compatibility with older logic until removed.
    """
    node_type: str = Field(default="PropertyAccessNode")
    path: List[str] = Field(default_factory=list)
    data_type: Optional[DataType] = Field(default=None)

    def is_function_call(self) -> bool:
        return self.get_method_access_node() is not None

    def get_property_path(self) -> List[str]:
        return self.path

    def get_method_access_node(self) -> Optional[MethodAccessNode]:
        current: Optional[Node] = self.value

        while current is not None:
            if isinstance(current, MethodAccessNode):
                return current
            if isinstance(current, PropertyAccessNode):
                current = current.value
                continue
            break

        return None

    def __str__(self) -> str:
        # If you have a real path, use it.
        if self.path:
            return ".".join(self.path)
        # Else fallback to legacy member_name/value rendering
        return super().__str__()