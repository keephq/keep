from typing import Any
import celpy.celparser
import lark
import celpy
from typing import List, cast

from keep.api.core.cel_to_sql.ast_nodes import ComparisonNode, ConstantNode, LogicalNode, MethodAccessNode, Node, ParenthesisNode, PropertyAccessNode, UnaryNode

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
            comparison_node.secondOperand = second_operand
            self.stack.append(comparison_node)

    def relation_lt(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.LT,
                secondOperand=None
            )
        )

    def relation_le(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.LE,
                secondOperand=None
            )
        )

    def relation_gt(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.GT,
                secondOperand=None
            )
        )

    def relation_ge(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.GE,
                secondOperand=None
            )
        )

    def relation_eq(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.EQ,
                secondOperand=None
            )
        )

    def relation_ne(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.NE,
                secondOperand=None
            )
        )

    def relation_in(self, tree: lark.Tree) -> None:
        self.stack.append(
            ComparisonNode(
                firstOperand = self.stack.pop(),
                operator = ComparisonNode.IN,
                secondOperand=None
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

            method = MethodAccessNode(member_name=right, args=exprlist)
            left.value = method

            self.member_access_stack.append(method)
        else:
            self.stack.append(f".{right}({exprlist})")

    def member_index(self, tree: lark.Tree) -> None:
        right = self.stack.pop()
        left = self.stack.pop()
        self.stack.append(f"{left}[{right}]")

    def member_object(self, tree: lark.Tree) -> None:
        if len(tree.children) == 2:
            fieldinits = self.stack.pop()
        else:
            fieldinits = ""
        left = self.stack.pop()
        self.stack.append(f"{left}{{{fieldinits}}}")

    def dot_ident_arg(self, tree: lark.Tree) -> None:
        if len(tree.children) == 2:
            exprlist = self.stack.pop()
        else:
            exprlist = ""
        left = cast(lark.Token, tree.children[0]).value
        self.stack.append(f".{left}({exprlist})")

    def dot_ident(self, tree: lark.Tree) -> None:
        left = cast(lark.Token, tree.children[0]).value
        self.stack.append(f".{left}")

    def ident_arg(self, tree: lark.Tree) -> None:
        if len(tree.children) == 2:
            exprlist = self.stack.pop()
        else:
            exprlist = ""

        left = cast(lark.Token, tree.children[0]).value
        self.stack.append(f"{left}({exprlist})")

    def ident(self, tree: lark.Tree) -> None:
        property_member = PropertyAccessNode(member_name=cast(lark.Token, tree.children[0]).value, value=None)
        self.member_access_stack.clear()
        self.stack.append(property_member)
        self.member_access_stack.append(property_member)

    def paren_expr(self, tree: lark.Tree) -> None:
        if self.stack:
            self.stack.append(ParenthesisNode(expression = self.stack.pop()))

    def list_lit(self, tree: lark.Tree) -> None:
        if self.stack:
            left = self.stack.pop()
            self.stack.append(f"[{left}]")

    def map_lit(self, tree: lark.Tree) -> None:
        if self.stack:
            left = self.stack.pop()
            self.stack.append(f"{{{left}}}")
        else:
            self.stack.append("{}")

    def exprlist(self, tree: lark.Tree) -> None:
        items = []

        for _ in tree.children:
            items.append(self.stack.pop())

        self.stack.append([item for item in reversed(items)])

    def fieldinits(self, tree: lark.Tree) -> None:
        names = cast(List[lark.Token], tree.children[::2])
        values = cast(List[lark.Token], tree.children[1::2])
        assert len(names) == len(values)
        pairs = reversed(list((n.value, self.stack.pop()) for n, v in zip(names, values)))
        items = ", ".join(f"{n}: {v}" for n, v in pairs)
        self.stack.append(items)

    def mapinits(self, tree: lark.Tree) -> None:
        """Note reversed pop order for values and keys."""
        keys = tree.children[::2]
        values = tree.children[1::2]
        assert len(keys) == len(values)
        pairs = reversed(list(
            {'value': self.stack.pop(), 'key': self.stack.pop()}
            for k, v in zip(keys, values)
        ))
        items = ", ".join(f"{k_v['key']}: {k_v['value']}" for k_v in pairs)
        self.stack.append(items)

    def literal(self, tree: lark.Tree) -> None:
        if tree.children:
            value: str = cast(lark.Token, tree.children[0]).value
            
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            self.stack.append(ConstantNode(value=value))

