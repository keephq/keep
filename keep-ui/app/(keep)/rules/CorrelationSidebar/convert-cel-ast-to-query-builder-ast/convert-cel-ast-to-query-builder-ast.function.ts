import { v4 as uuidv4 } from "uuid";
import { CelAst } from "@/utils/cel-ast";
import { DefaultRuleGroupType } from "react-querybuilder";

function mapOperator(op: string): string {
  switch (op) {
    case "==":
      return "=";
    case "!=":
      return "!=";
    case ">":
      return ">";
    case "<":
      return "<";
    case ">=":
      return ">=";
    case "<=":
      return "<=";
    case "contains":
      return "contains";
    case "startsWith":
      return "beginsWith";
    case "endsWith":
      return "endsWith";
    default:
      return op;
  }
}

function visitUnaryNode(node: CelAst.UnaryNode): DefaultRuleGroupType {
  if (node.operator !== CelAst.UnaryNodeOperator.NOT) {
    throw new Error("Unsupported operator: " + node.operator);
  }

  let operand = (node as CelAst.UnaryNode).operand;

  if (operand?.node_type === "ParenthesisNode") {
    operand = (operand as CelAst.ParenthesisNode).expression;
  }

  if (operand?.node_type === "ComparisonNode") {
    const field = (
      (operand as CelAst.ComparisonNode)
        .first_operand as CelAst.PropertyAccessNode
    )?.path.join(".");
    const value = (
      (operand as CelAst.ComparisonNode).second_operand as CelAst.ConstantNode
    )?.value;
    let operator: string = "";
    switch ((operand as CelAst.ComparisonNode).operator) {
      case CelAst.ComparisonNodeOperator.IN:
        operator = "notIn";
        break;
      case CelAst.ComparisonNodeOperator.CONTAINS:
        operator = "doesNotContain";
        break;
      case CelAst.ComparisonNodeOperator.STARTS_WITH:
        operator = "doesNotBeginWith";
        break;
      case CelAst.ComparisonNodeOperator.ENDS_WITH:
        operator = "doesNotEndWith";
        break;
    }

    return {
      combinator: "and",
      rules: [
        {
          field,
          operator,
          value,
          id: uuidv4(),
        } as any,
      ],
    };
  }

  throw new Error("UnaryNode with unknown operand: " + node.node_type);
}

function visitComparisonNode(
  node: CelAst.ComparisonNode
): DefaultRuleGroupType {
  const field = (
    (node as CelAst.ComparisonNode).first_operand as CelAst.PropertyAccessNode
  )?.path.join(".");
  const operator = (node as CelAst.ComparisonNode).operator;
  const value = (
    (node as CelAst.ComparisonNode).second_operand as CelAst.ConstantNode
  )?.value;
  let queryBuilderField = null;

  if (operator == CelAst.ComparisonNodeOperator.NE && value == null) {
    queryBuilderField = {
      field,
      operator: "notNull",
      id: uuidv4(),
    } as any;
  } else if (operator == CelAst.ComparisonNodeOperator.EQ && value == null) {
    queryBuilderField = {
      field,
      operator: "null",
      id: uuidv4(),
    } as any;
  } else {
    queryBuilderField = {
      field,
      operator: mapOperator((node as CelAst.ComparisonNode).operator),
      value,
      id: uuidv4(),
    } as any;
  }

  return {
    combinator: "and",
    rules: [queryBuilderField],
  };
}

function visitLogicalNode(node: CelAst.LogicalNode): DefaultRuleGroupType {
  const left = visitCelAstNode(
    ((node as CelAst.LogicalNode).left as any).expression ??
      (node as CelAst.LogicalNode).left
  );
  const right = visitCelAstNode(
    ((node as CelAst.LogicalNode).right as any).expression ??
      (node as CelAst.LogicalNode).right
  );
  const combinator =
    (node as CelAst.LogicalNode).operator === CelAst.LogicalNodeOperator.OR
      ? "or"
      : "and";

  const rules = [];

  if (left.combinator == combinator || left.rules.length <= 1) {
    rules.push(...left.rules);
  } else {
    rules.push(left);
  }

  if (right.combinator == combinator || right.rules.length <= 1) {
    rules.push(...right.rules);
  } else {
    rules.push(right);
  }

  return {
    combinator,
    rules: rules,
  };
}

export function visitCelAstNode(node: CelAst.Node): DefaultRuleGroupType {
  switch (node.node_type) {
    case "LogicalNode": {
      return visitLogicalNode(node as CelAst.LogicalNode);
    }
    case "ParenthesisNode": {
      return visitCelAstNode((node as CelAst.ParenthesisNode).expression);
    }
    case "ComparisonNode": {
      return visitComparisonNode(node as CelAst.ComparisonNode);
    }
    case "UnaryNode": {
      return visitUnaryNode(node as CelAst.UnaryNode);
    }

    default:
      throw new Error(`Unsupported node type: ${node.node_type}`);
  }
}

export function convertCelAstToQueryBuilderAst(
  node: CelAst.Node
): DefaultRuleGroupType {
  let rulesGroup = visitCelAstNode(node);

  if (rulesGroup.combinator === "or") {
    // React Query Builder requires all rules to be within "and" combinator groups to function correctly.
    // Therefore, if an "or" group contains any element that is not itself an "or" or "and" group,
    // we wrap that element in a new "and" group to ensure compatibility.
    rulesGroup.rules = rulesGroup.rules.map((rule) => {
      if (!(rule as any).combinator) {
        return {
          combinator: "and",
          rules: [rule],
        };
      }

      return rule;
    });
  }

  if (rulesGroup.combinator == "and") {
    rulesGroup = {
      combinator: "and",
      rules: [rulesGroup],
    };
  }

  return rulesGroup;
}
