import re
from typing import Any
import celpy.celparser
import lark
import celpy
from typing import List, cast
from dateutil.parser import parse

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    LogicalNode,
    LogicalNodeOperator,
    Node,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
    UnaryNodeOperator,
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
            self.stack.append(
                LogicalNode(left=left, operator=LogicalNodeOperator.OR, right=right)
            )

    def conditionaland(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        else:
            right = self.stack.pop()
            left = self.stack.pop()
            self.stack.append(
                LogicalNode(left=left, operator=LogicalNodeOperator.AND, right=right)
            )

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
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.LT,
                second_operand=None,
            )
        )

    def relation_le(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.LE,
                second_operand=None,
            )
        )

    def relation_gt(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.GT,
                second_operand=None,
            )
        )

    def relation_ge(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.GE,
                second_operand=None,
            )
        )

    def relation_eq(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.EQ,
                second_operand=None,
            )
        )

    def relation_ne(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.NE,
                second_operand=None,
            )
        )

    def relation_in(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                first_operand=self.stack.pop(),
                operator=ComparisonNodeOperator.IN,
                second_operand=None,
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
        self.stack.append(UnaryNode(operator=UnaryNodeOperator.NOT, operand=None))

    def unary_neg(self, tree: lark.Tree) -> None:
        self.stack.append(UnaryNode(operator=UnaryNodeOperator.NEG, operand=None))

    def member_dot(self, tree: lark.Tree) -> None:
        right = cast(lark.Token, tree.children[1]).value

        if self.member_access_stack:
            property_member: PropertyAccessNode = self.member_access_stack.pop()
            new_property_access_node = PropertyAccessNode(
                path=property_member.path + [right]
            )
            self.stack.pop()
            self.stack.append(new_property_access_node)
            self.member_access_stack.append(new_property_access_node)

    def member_dot_arg(self, tree: lark.Tree) -> None:
        if len(tree.children) == 3:
            exprlist = self.stack.pop()
        else:
            exprlist = []
        right = cast(lark.Token, tree.children[1]).value
        if self.member_access_stack:
            if right.lower() in [
                ComparisonNodeOperator.CONTAINS.value.lower(),
                ComparisonNodeOperator.STARTS_WITH.value.lower(),
                ComparisonNodeOperator.ENDS_WITH.value.lower(),
            ]:
                self.stack.append(
                    ComparisonNode(
                        first_operand=self.stack.pop(),
                        operator=right,
                        second_operand=exprlist[0],
                    )
                )
                return

            raise NotImplementedError(f"Method '{right}' not implemented")

        else:
            raise ValueError("No member access stack")

    def member_index(self, tree: lark.Tree) -> None:
        right = self.stack.pop()
        left = self.stack.pop()

        if isinstance(right, ConstantNode):
            right = right.value

        prop_access_node: PropertyAccessNode = left
        self.stack.append(left)
        self.member_access_stack.append(
            PropertyAccessNode(path=prop_access_node.path + [str(right)])
        )

    def member_object(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Member object not implemented")

    def dot_ident_arg(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Dot ident arg not implemented")

    def dot_ident(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Dot ident not implemented")

    def ident_arg(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Ident arg not implemented")

    def ident(self, tree: lark.Tree) -> None:
        property_member = PropertyAccessNode(
            path=[cast(lark.Token, tree.children[0]).value]
        )
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
                value = re.sub(r'\\(["\'])', r"\1", value)
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
