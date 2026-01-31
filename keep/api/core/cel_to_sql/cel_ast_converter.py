import logging
import re
from datetime import datetime
from typing import Any, List, Optional, cast

import celpy
import lark
from dateutil.parser import parse as dt_parse  # fallback only

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

logger = logging.getLogger(__name__)

iso_regex = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"T"
    r"(\d{2}):(\d{2}):(\d{2})"
    r"(?:\.(\d+))?"
    r"(?:Z|[+-]\d{2}:\d{2})?$"
)

datetime_regex = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:\s(\d{2}):(\d{2}):(\d{2}))?$"
)

_METHOD_TO_OP: dict[str, ComparisonNodeOperator] = {
    "contains": ComparisonNodeOperator.CONTAINS,
    "startswith": ComparisonNodeOperator.STARTS_WITH,
    "endswith": ComparisonNodeOperator.ENDS_WITH,
}


class CelToAstConverter(lark.visitors.Visitor_Recursive):
    """Convert CEL -> internal AST nodes (Node graph)."""

    MAX_STACK_DEPTH = 10_000  # prevents weird DoS via huge pushes

    @classmethod
    def convert_to_ast(cls, cel: str) -> Node:
        inst = cls()
        try:
            celpy_ast = inst.celpy_env.compile(cel)
            inst.visit(celpy_ast)
            if len(inst.stack) != 1 or not isinstance(inst.stack[0], Node):
                raise ValueError(
                    f"CEL AST conversion ended in invalid stack state: "
                    f"size={len(inst.stack)}, top_type={type(inst.stack[0]).__name__ if inst.stack else None}"
                )
            return cast(Node, inst.stack[0])
        except Exception:
            logger.exception('Error converting CEL to AST: "%s"', cel)
            raise

    def __init__(self) -> None:
        self.celpy_env = celpy.Environment()
        self.stack: List[Any] = []  # contains Node or list[Node]
        self.member_access_stack: List[PropertyAccessNode] = []

    # ---------- stack helpers ----------
    def _push(self, item: Any) -> None:
        self.stack.append(item)
        if len(self.stack) > self.MAX_STACK_DEPTH:
            raise ValueError(f"CEL AST stack overflow (>{self.MAX_STACK_DEPTH})")

    def _pop(self) -> Any:
        if not self.stack:
            raise ValueError("CEL AST stack underflow (pop on empty stack)")
        return self.stack.pop()

    def _pop_node(self) -> Node:
        val = self._pop()
        if not isinstance(val, Node):
            raise ValueError(f"Expected Node on stack, got {type(val).__name__}: {val!r}")
        return val

    def _pop_node_list(self) -> List[Node]:
        val = self._pop()
        if val is None:
            return []
        if isinstance(val, list) and all(isinstance(x, Node) for x in val):
            return cast(List[Node], val)
        raise ValueError(f"Expected list[Node] on stack, got {type(val).__name__}: {val!r}")

    # ---------- grammar visitors ----------
    def expr(self, tree: lark.Tree) -> None:
        # Ternary operator appears here. If you don’t support it downstream, fail loudly.
        if len(tree.children) == 1:
            return
        raise NotImplementedError("Ternary (cond ? a : b) is not supported by this SQL converter")

    def conditionalor(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        right = self._pop_node()
        left = self._pop_node()
        self._push(LogicalNode(left=left, operator=LogicalNodeOperator.OR, right=right))

    def conditionaland(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        right = self._pop_node()
        left = self._pop_node()
        self._push(LogicalNode(left=left, operator=LogicalNodeOperator.AND, right=right))

    def relation(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        second = self._pop_node()
        comp = self._pop()
        if not isinstance(comp, ComparisonNode):
            raise ValueError(f"Expected ComparisonNode before relation RHS, got {type(comp).__name__}")
        comp.second_operand = second
        self._push(comp)

    def relation_lt(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.LT, second_operand=None))

    def relation_le(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.LE, second_operand=None))

    def relation_gt(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.GT, second_operand=None))

    def relation_ge(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.GE, second_operand=None))

    def relation_eq(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.EQ, second_operand=None))

    def relation_ne(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.NE, second_operand=None))

    def relation_in(self, tree: lark.Tree) -> None:
        self._push(ComparisonNode(first_operand=self._pop_node(), operator=ComparisonNodeOperator.IN, second_operand=None))

    # Arithmetic: reject until you implement ArithmeticNode in your AST + SQL builder
    def addition(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        raise NotImplementedError("Arithmetic (+/-) not supported by SQL converter")

    def multiplication(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        raise NotImplementedError("Arithmetic (*//%) not supported by SQL converter")

    def unary(self, tree: lark.Tree) -> None:
        if len(tree.children) == 1:
            return
        operand = self._pop_node()
        un = self._pop()
        if not isinstance(un, UnaryNode):
            raise ValueError(f"Expected UnaryNode frame, got {type(un).__name__}")
        un.operand = operand
        self._push(un)

    def unary_not(self, tree: lark.Tree) -> None:
        self._push(UnaryNode(operator=UnaryNodeOperator.NOT, operand=None))

    def unary_neg(self, tree: lark.Tree) -> None:
        raise NotImplementedError("Unary negation (-x) not supported by SQL converter")

    def ident(self, tree: lark.Tree) -> None:
        name = cast(lark.Token, tree.children[0]).value
        node = PropertyAccessNode(path=[name])
        self.member_access_stack.clear()
        self._push(node)
        self.member_access_stack.append(node)

    def member_dot(self, tree: lark.Tree) -> None:
        # left.right chaining
        right = cast(lark.Token, tree.children[1]).value
        if not self.member_access_stack:
            raise ValueError("member_dot without active base identifier")

        base = self.member_access_stack.pop()
        new_node = PropertyAccessNode(path=base.path + [right])

        # replace top of main stack with new_node (validated)
        top = self._pop_node()
        if not isinstance(top, PropertyAccessNode):
            raise ValueError(f"Expected PropertyAccessNode on stack for member access, got {type(top).__name__}")
        self._push(new_node)
        self.member_access_stack.append(new_node)

    def member_index(self, tree: lark.Tree) -> None:
        idx = self._pop()
        base = self._pop_node()
        if isinstance(idx, ConstantNode):
            idx = idx.value
        if not isinstance(base, PropertyAccessNode):
            raise ValueError(f"Indexing only supported on PropertyAccessNode, got {type(base).__name__}")
        new_node = PropertyAccessNode(path=base.path + [str(idx)])
        self._push(new_node)
        self.member_access_stack.append(new_node)

    def member_dot_arg(self, tree: lark.Tree) -> None:
        # method calls like alert.name.contains("x")
        args = self._pop_node_list() if len(tree.children) == 3 else []
        method = cast(lark.Token, tree.children[1]).value
        method_key = method.lower()

        if not self.member_access_stack:
            raise ValueError("Method call without member base")

        op = _METHOD_TO_OP.get(method_key)
        if op is None:
            raise NotImplementedError(f"Method '{method}' not implemented")

        if len(args) != 1 or not isinstance(args[0], ConstantNode):
            raise ValueError(f"{method} expects exactly 1 constant argument")

        first_operand = self._pop_node()
        self._push(ComparisonNode(first_operand=first_operand, operator=op, second_operand=args[0]))

    def ident_arg(self, tree: lark.Tree) -> None:
        token_value = cast(lark.Token, tree.children[0]).value
        if token_value == UnaryNodeOperator.HAS.value:
            # celpy tends to provide args as exprlist or direct node depending on grammar path.
            operand = self._pop_node()
            self._push(UnaryNode(operator=UnaryNodeOperator.HAS, operand=operand))
            return
        raise NotImplementedError(f"ident_arg not implemented for: {token_value}")

    def paren_expr(self, tree: lark.Tree) -> None:
        self._push(ParenthesisNode(expression=self._pop_node()))

    def exprlist(self, tree: lark.Tree) -> None:
        # items were pushed in order; popping reverses them, so reverse back
        items: List[Node] = []
        for _ in tree.children:
            items.append(self._pop_node())
        items.reverse()
        self._push(items)

    def list_lit(self, tree: lark.Tree) -> None:
        # list literal: exprlist already returns items in correct order
        return

    def literal(self, tree: lark.Tree) -> None:
        if not tree.children:
            return
        raw = cast(lark.Token, tree.children[0]).value
        self._push(self.to_constant_node(raw))

    # ---------- literal conversion ----------
    def to_constant_node(self, value: str) -> ConstantNode:
        if value in ("null", "NULL"):
            return ConstantNode(value=None)

        if value in ("true", "false"):
            return ConstantNode(value=(value == "true"))

        # quoted string
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            s = value[1:-1]
            # unescape \" or \' inside
            s = re.sub(r'\\(["\'])', r"\1", s)
            # datetime detection
            if not self.is_number(s) and self.is_date(s):
                dt = self._parse_datetime_fast(s)
                return ConstantNode(value=dt)
            return ConstantNode(value=s)

        # numbers
        if "." in value and self.is_float(value):
            return ConstantNode(value=float(value))
        if self.is_number(value):
            return ConstantNode(value=int(value))

        raise ValueError(f"Unknown literal type: {value!r}")

    def _parse_datetime_fast(self, s: str) -> datetime:
        # Fast path for ISO strings; supports trailing Z
        try:
            if s.endswith("Z"):
                s2 = s[:-1] + "+00:00"
                return datetime.fromisoformat(s2)
            return datetime.fromisoformat(s)
        except Exception:
            # fallback
            return dt_parse(s)

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
        return bool(iso_regex.match(value) or datetime_regex.match(value))