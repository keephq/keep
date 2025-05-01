import datetime
import pytest

from keep.api.core.cel_to_sql.ast_nodes import (
    ComparisonNode,
    ComparisonNodeOperator,
    ConstantNode,
    LogicalNode,
    LogicalNodeOperator,
    MethodAccessNode,
    ParenthesisNode,
    PropertyAccessNode,
    UnaryNode,
    UnaryNodeOperator,
)
from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter


@pytest.mark.parametrize(
    "cel, operator, expected_constant_type, expected_constant_value",
    [
        ("fakeProp == 'fake alert'", ComparisonNodeOperator.EQ, str, "fake alert"),
        (
            "fakeProp == 'It\\'s value with escaped single-quote'",
            ComparisonNodeOperator.EQ,
            str,
            "It's value with escaped single-quote",
        ),
        (
            'fakeProp == "It\\"s value with escaped double-quote"',
            ComparisonNodeOperator.EQ,
            str,
            'It"s value with escaped double-quote',
        ),
        ("fakeProp == true", ComparisonNodeOperator.EQ, bool, True),
        ("fakeProp == 12349983", ComparisonNodeOperator.EQ, int, 12349983),
        ("fakeProp == 1234.9983", ComparisonNodeOperator.EQ, float, 1234.9983),
        (
            "fakeProp == 'MON'",
            ComparisonNodeOperator.EQ,
            str,
            "MON",
        ),  # check that day-of-week short names do not get converted to dates
        ("fakeProp == 'mon'", ComparisonNodeOperator.EQ, str, "mon"),
        (
            "fakeProp == '2025-01-20'",
            ComparisonNodeOperator.EQ,
            datetime.datetime,
            datetime.datetime(2025, 1, 20),
        ),
        (
            "fakeProp == '2025-01-20T14:35:27.123456'",
            ComparisonNodeOperator.EQ,
            datetime.datetime,
            datetime.datetime(2025, 1, 20, 14, 35, 27, 123456),
        ),
        ("fakeProp != 'fake alert'", ComparisonNodeOperator.NE, str, "fake alert"),
        ("fakeProp > 'fake alert'", ComparisonNodeOperator.GT, str, "fake alert"),
        ("fakeProp >= 'fake alert'", ComparisonNodeOperator.GE, str, "fake alert"),
        ("fakeProp < 'fake alert'", ComparisonNodeOperator.LT, str, "fake alert"),
        ("fakeProp <= 'fake alert'", ComparisonNodeOperator.LE, str, "fake alert"),
    ],
)
def test_simple_comparison_node(cel, operator, expected_constant_type, expected_constant_value):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, ComparisonNode)
    assert actual.operator == operator
    
    # Check that second operand is a ConstantNode
    assert isinstance(actual.second_operand, ConstantNode)
    assert isinstance(actual.second_operand.value, expected_constant_type)
    assert actual.second_operand.value == expected_constant_value

    # Check that first operand is a PropertyAccessNode
    assert isinstance(actual.first_operand, PropertyAccessNode)
    assert actual.first_operand.member_name == "fakeProp"
    assert actual.first_operand.value is None

@pytest.mark.parametrize("cel, args", [
    ("fakeProp in ['string', 12345, true]", ["string", 12345, True]),
])
def test_simple_comparison_node_in(cel, args):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, ComparisonNode)
    assert actual.operator == ComparisonNodeOperator.IN

    # Check that second operand is a list
    assert isinstance(actual.second_operand, list)

    # verify that each element in the list is a ConstantNode with the correct value and type
    for i, arg in enumerate(actual.second_operand):
        assert isinstance(arg, ConstantNode)
        assert type(arg.value) == type(args[i])
        assert arg.value == args[i]


@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!fakeProp", UnaryNodeOperator.NOT),
        ("-fakeProp", UnaryNodeOperator.NEG),
    ],
)
def test_simple_unary_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, UnaryNode)
    assert actual.operator == operator

    # Check that first operand is a PropertyAccessNode
    assert isinstance(actual.operand, PropertyAccessNode)
    assert actual.operand.member_name == "fakeProp"
    assert actual.operand.value is None


@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!firstFakeProp && !secondFakeProp", LogicalNodeOperator.AND),
        ("!firstFakeProp || !secondFakeProp", LogicalNodeOperator.OR),
    ],
)
def test_simple_logical_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a LogicalNode
    assert isinstance(actual, LogicalNode)
    assert actual.operator == operator

    # Check that left is UnaryNode with NOT operator
    assert isinstance(actual.left, UnaryNode)
    assert actual.left.operator == UnaryNodeOperator.NOT

    # Check that left.operand is PropertyAccessNode
    assert isinstance(actual.left.operand, PropertyAccessNode)
    assert actual.left.operand.member_name == "firstFakeProp"
    assert actual.left.operand.value is None

    # Check that right is UnaryNode with NOT operator
    assert isinstance(actual.right, UnaryNode)
    assert actual.right.operator == UnaryNodeOperator.NOT

    # Check that left.operand is PropertyAccessNode
    assert isinstance(actual.right.operand, PropertyAccessNode)
    assert actual.right.operand.member_name == "secondFakeProp"
    assert actual.right.operand.value is None

@pytest.mark.parametrize("cel, method_name, args", [
    ("fakeProp.contains('CPU')", "contains", ["CPU"]),
    ("fakeProp.anything('string', 123, false)", "anything", ["string", 123, False]),
])
def test_method_access_node(cel, method_name, args):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a PropertyAccessNode where value is MethodAccessNode
    assert isinstance(actual, PropertyAccessNode)
    assert actual.member_name == "fakeProp"
    assert isinstance(actual.value, MethodAccessNode)
    assert actual.value.member_name == method_name

    # Check that args are correct
    for i, arg in enumerate(actual.value.args):
        assert isinstance(arg, ConstantNode)
        assert type(arg.value) == type(args[i])
        assert arg.value == args[i]


@pytest.mark.parametrize(
    "cel, operator",
    [
        ("!(fakeProp)", UnaryNodeOperator.NOT),
        ("-(fakeProp)", UnaryNodeOperator.NEG),
    ],
)
def test_parenthesis_node(cel, operator):
    actual = CelToAstConverter.convert_to_ast(cel)

    # Check that the root node is a ComparisonNode
    assert isinstance(actual, UnaryNode)
    assert actual.operator == operator

    # Check that the operand is ParenthesesNode
    assert isinstance(actual.operand, ParenthesisNode)

    # Check that the operand.expression is PropertyAccessNode
    assert isinstance(actual.operand.expression, PropertyAccessNode)
    assert actual.operand.expression.member_name == "fakeProp"
    assert actual.operand.expression.value is None
