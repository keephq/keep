import re
from typing import Any
import celpy.celparser
import lark
import celpy
from typing import List, cast
from dateutil.parser import parse

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ConstantNode,
    IndexAccessNode,
    LogicalNode,
    MethodAccessNode,
    Node,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
)

# Matches such strings:
# '2025-03-23T15:42:00'
# '2025-03-23T15:42:00Z'
# '2025-03-23T15:42:00.123Z'
# '2025-03-23T15:42:00+02:00'
# '2025-03-23T15:42:00.456-05:30'
iso_regex = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"  # Date: YYYY-MM-DD
    r"T"  # T separator
    r"(\d{2}):(\d{2}):(\d{2})"  # Time: hh:mm:ss
    r"(?:\.(\d+))?"  # Optional fractional seconds
    r"(?:Z|[+-]\d{2}:\d{2})?$"  # Optional timezone (Z or ±hh:mm)
)

# Matches such strings:
# '2025-03-23 15:42:00'
# '1999-01-01 00:00:00'
# '2025-01-20'
datetime_regex = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"  # Date: YYYY-MM-DD
    r"(?:\s(\d{2}):(\d{2}):(\d{2}))?$"  # Optional time: HH:MM:SS
)


class CelToAstConverter(lark.visitors.Visitor_Recursive):
    """Dump a CEL AST creating a close approximation to the original source."""

    @classmethod
    def convert_to_ast(cls_, cel: str) -> Node:
        d = cls_()
        celpy_ast = d.celpy_env.compile(cel)
        d.visit(celpy_ast)
        return d.stack[0]

    def __init__(self) -> None:
        self.celpy_env = celpy.Environment()
        self.stack: List[Any] = []
        self.member_access_stack: List[str] = []

    def expr(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left = self.stack.pop()
            cond = self.stack.pop()
            self.stack.append(
                f"{cond} ? {left} : {right}"
            )

    def conditionalor(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left = self.stack.pop()
            self.stack.append(LogicalNode(
                left = left,
                operator = LogicalNode.OR,
                right = right
            ))

    def conditionaland(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left = self.stack.pop()
            self.stack.append(LogicalNode(
                left = left,
                operator = LogicalNode.AND,
                right = right
            ))

    def relation(self, tree: lark.Tree) -> None:
        # self.member_access_stack.clear()

        if len(tree.children) == 1:
            return
        else:
            second_operand = self.stack.pop()
            comparison_node: ComparisonNode = self.stack.pop()
            comparison_node.second_operand = second_operand
            self.stack.append(comparison_node)

    def relation_lt(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.LT,
                second_operand=None
            )
        )

    def relation_le(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.LE,
                second_operand=None
            )
        )

    def relation_gt(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.GT,
                second_operand=None
            )
        )

    def relation_ge(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.GE,
                second_operand=None
            )
        )

    def relation_eq(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.EQ,
                second_operand=None
            )
        )

    def relation_ne(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.NE,
                second_operand=None
            )
        )

    def relation_in(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand = self.stack.pop(),
                operator = ComparisonNode.IN,
                second_operand=None
            )
        )

    def addition(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left: dict = self.stack.pop()
            left['right'] = right
            self.stack.append(left)

    def addition_add(self, tree: lark.Tree) -> None:
        left = self.stack.pop()
        self.stack.append({
            'left': left,
            'operator': 'ADD'
        })

    def addition_sub(self, tree: lark.Tree) -> None:
        left = self.stack.pop()
        self.stack.append({
            'left': left,
            'operator': 'SUB'
        })

    def multiplication(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left: dict = self.stack.pop()
            left['right'] = right
            self.stack.append(left)

    def multiplication_mul(self, tree: lark.Tree) -> None:
        left = self.stack.pop()
        self.stack.append({
            'left': left,
            'operator': 'MUL'
        })

    def multiplication_div(self, tree: lark.Tree) -> None:
        left = self.stack.pop()
        self.stack.append({
            'left': left,
            'operator': 'DIV'
        })

    def multiplication_mod(self, tree: lark.Tree) -> None:
        left = self.stack.pop()
        self.stack.append({
            'left': left,
            'operator': 'MOD'
        })

    def unary(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            operand = self.stack.pop()
            unaryNode: UnaryNode = self.stack.pop()
            unaryNode.operand = operand
            self.stack.append(unaryNode)

    def unary_not(self, tree: lark.Tree) -> None:
        self.stack.append(
            UnaryNode(operator=UnaryNode.NOT, operand=None)
        )

    def unary_neg(self, tree: lark.Tree) -> None:
        self.stack.append(
            UnaryNode(operator=UnaryNode.NEG, operand=None)
        )

    def member_dot(self, tree: lark.Tree) -> None:
        right = cast(lark.Token, tree.children[1]).value

        if self.member_access_stack:
            property_member: PropertyAccessNode = self.member_access_stack.pop()
            property_value = PropertyAccessNode(member_name=right, value=None)
            property_member.value = property_value
            self.member_access_stack.append(property_value)

    def member_dot_arg(self, tree: lark.Tree) -> None:
        if len(tree.children) == 3:
            exprlist = self.stack.pop()
        else:
            exprlist = []
        right = cast(lark.Token, tree.children[1]).value
        if self.member_access_stack:
            left: PropertyAccessNode = self.member_access_stack.pop()

            method = MethodAccessNode(member_name=right, args=[item for item in reversed(exprlist)])
            left.value = method

            self.member_access_stack.append(method)
        else:
            raise ValueError("No member access stack")

    def member_index(self, tree: lark.Tree) -> None:
        right = self.stack.pop()
        left = self.stack.pop()

        if isinstance(right, ConstantNode):
            right = right.value

        prop_access_node = left

        while prop_access_node.value is not None:
            prop_access_node = prop_access_node.value

        prop_access_node.value = IndexAccessNode(str(right), None)

        self.stack.append(left)
        self.member_access_stack.append(prop_access_node.value)

    def member_object(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Member object not implemented")

    def dot_ident_arg(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Dot ident arg not implemented")

    def dot_ident(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Dot ident not implemented")

    def ident_arg(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Ident arg not implemented")

    def ident(self, tree: lark.Tree) -> None:
        property_member = PropertyAccessNode(member_name=cast(lark.Token, tree.children[0]).value, value=None)
        self.member_access_stack.clear()
        self.stack.append(property_member)
        self.member_access_stack.append(property_member)

    def paren_expr(self, tree: lark.Tree) -> None:
        if not self.stack:
            raise ValueError("Cannot handle parenthesis expression without stack")

        self.stack.append(ParenthesisNode(expression=self.stack.pop()))

    def list_lit(self, tree: lark.Tree) -> None:
        if self.stack:
            left = self.stack.pop()
            self.stack.append([item for item in reversed(left)])

    def map_lit(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Map literal not implemented")

    def exprlist(self, tree: lark.Tree) -> None:
        list_items = list(self.stack.pop() for _ in tree.children)
        self.stack.append(list_items)

    def fieldinits(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Fieldinits not implemented")

    def mapinits(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Mapinits not implemented")

    def literal(self, tree: lark.Tree) -> None:
        if tree.children:
            value = cast(lark.Token, tree.children[0]).value
            constant_node = self.to_constant_node(value)
            self.stack.append(constant_node)

    def to_constant_node(self, value: str) -> ConstantNode:
        if value in ['null', 'NULL']:
            value = None
        elif (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

            if not self.is_number(value) and self.is_date(value):
                value = parse(value)
            else:
                # this code is to handle the case when string literal contains escaped single/double quotes
                value = value.encode("utf-8").decode("unicode_escape")
        elif value == 'true' or value == 'false':
            value = value == 'true'
        elif '.' in value and self.is_float(value):
            value = float(value)
        elif self.is_number(value):
            value = int(value)
        else:
            raise ValueError(f"Unknown literal type: {value}")

        return ConstantNode(value=value)

    def is_number(self, value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

    def is_float(self, value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False

    def is_date(self, value: str) -> bool:
        return iso_regex.match(value) or datetime_regex.match(value)
