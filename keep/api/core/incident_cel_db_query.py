import enum
from typing import Any
import celpy.celparser
from lark import Token, Tree, Visitor
import lark
from sqlalchemy.orm import Query
import celpy
from typing import List, cast

class ConstantNode:
    def __init__(self, value: Any):
        self.value = value

class ParenthesisNode:
    def __init__(self, expression: Any):
        self.expression = expression

class LogicalNode:
    AND = '&&'
    OR = '||'

    def __init__(self, left: Any, operator: str, right: Any):
        self.left = left
        self.operator = operator
        self.right = right

class ComparisonNode:
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

class UnaryNode:
    NOT = '!'
    NEG = '-'

    def __init__(self, operator: str, operand: Any):
        self.operator = operator
        self.operand = operand
    
class MemberAccessNode:
    def __init__(self, member_name: str):
        self.member_name = member_name


class PropertyAccessNode(MemberAccessNode):
    def __init__(self, member_name, value: Any):
        self.value = value
        super().__init__(member_name)

class MethodAccessNode(MemberAccessNode):
    def __init__(self, member_name, args: List[str] = None):
        self.args = args
        super().__init__(member_name)
        
def expression_to_str(node: Any) -> str:
    if isinstance(node, LogicalNode):
        return f"{expression_to_str(node.left)} {node.operator} {expression_to_str(node.right)}"
    elif isinstance(node, ComparisonNode):
        return f"{expression_to_str(node.firstOperand)} {node.operator} {expression_to_str(node.secondOperand)}"
    elif isinstance(node, UnaryNode):
        return f"{node.operator}{expression_to_str(node.operand)}"
    elif isinstance(node, PropertyAccessNode):
        if node.value:
            return f"{node.member_name}.{expression_to_str(node.value)}"
        
        return node.member_name
    elif isinstance(node, MethodAccessNode):
        args = []
        for argNode in node.args:
            args.append(expression_to_str(argNode))

        return f"{node.member_name}({', '.join(args)})"
    elif isinstance(node, ParenthesisNode):
        return f"({expression_to_str(node.expression)})"
    elif isinstance(node, ConstantNode):
        return node.value
    else:
        return str(node)
    

class SimpleNodesAST(lark.visitors.Visitor_Recursive):
    """Dump a CEL AST creating a close approximation to the original source."""

    @classmethod
    def display(cls_, ast: lark.Tree) -> str:
        d = cls_()
        d.visit(ast)
        return d.stack[0]

    def __init__(self) -> None:
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


def enrich_with_filter_from_cel(input_query: Query[Any], cel: str) -> Query[Any]:
    # demo()
    celpy_env = celpy.Environment()
    ast = celpy_env.compile(cel)
    dumast = SimpleNodesAST()
    dumast.visit(ast)
    result = dumast.stack[0]

    strExp = expression_to_str(result)

    return None

enrich_with_filter_from_cel(None, '((((((pudel.bad == "fusk")))))) && alert.first.second.third.contains("gnida", "blyadina")')

def visit_tree(tree):
    res = ''
    if isinstance(tree, Tree):
        for child in tree.children:
           res += str(visit_tree(child)) + '  '
    elif isinstance(tree, Token):
        return str(tree)

def visint_expression(node: celpy.Expression, query: Query[Any]) -> Query[Any]:
    indent = 3
    if not node:
        return
    prefix = "  " * indent
    # Print basic node information (e.g., type, value, operator)
    print(f"{prefix}Node Type: {node.WhichOneof('expr_kind')}")
    if node.HasField("constant_expr"):
        print(f"{prefix}  Constant: {node.constant_expr}")
    elif node.HasField("ident_expr"):
        print(f"{prefix}  Identifier: {node.ident_expr.name}")
    elif node.HasField("call_expr"):
        print(f"{prefix}  Function: {node.call_expr.function}")
        print(f"{prefix}  Arguments:")
        for arg in node.call_expr.args:
            visint_expression(arg, query)
    return query