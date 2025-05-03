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
    default:
      return op;
  }
}

export function convertCelAstToQueryBuilderAst(
  node: CelAst.Node
): DefaultRuleGroupType {
  switch (node.node_type) {
    case "LogicalNode": {
      const left = convertCelAstToQueryBuilderAst(
        ((node as CelAst.LogicalNode).left as any).expression ??
          (node as CelAst.LogicalNode).left
      );
      const right = convertCelAstToQueryBuilderAst(
        ((node as CelAst.LogicalNode).right as any).expression ??
          (node as CelAst.LogicalNode).right
      );
      const combinator =
        (node as CelAst.LogicalNode).operator === CelAst.LogicalNodeOperator.OR
          ? "or"
          : "and";

      const rules = [];

      if (left.combinator == combinator) {
        rules.push(...left.rules);
      } else {
        rules.push(left);
      }

      if (right.combinator == combinator) {
        rules.push(...right.rules);
      } else {
        rules.push(right);
      }

      return {
        combinator,
        rules: rules,
      };
    }

    case "ParenthesisNode": {
      return convertCelAstToQueryBuilderAst(
        (node as CelAst.ParenthesisNode).expression
      );
    }

    case "ComparisonNode": {
      const field = (
        (node as CelAst.ComparisonNode)
          .first_operand as CelAst.PropertyAccessNode
      )?.path.join(".");
      const operator = mapOperator((node as CelAst.ComparisonNode).operator);
      const value = (
        (node as CelAst.ComparisonNode).second_operand as CelAst.ConstantNode
      )?.value;
      let queryBuilderField = null;

      if (operator == CelAst.ComparisonNodeOperator.NE && value == null) {
        queryBuilderField = {
          field,
          operator: "notNull",
          value,
          id: uuidv4(),
        } as any;
      } else if (
        operator == CelAst.ComparisonNodeOperator.EQ &&
        value == null
      ) {
        queryBuilderField = {
          field,
          operator: "null",
          value,
          id: uuidv4(),
        } as any;
      } else {
        queryBuilderField = {
          field,
          operator,
          value,
          id: uuidv4(),
        } as any;
      }

      return {
        combinator: "and",
        rules: [queryBuilderField],
      };
    }

    case "UnaryNode": {
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
          (operand as CelAst.ComparisonNode)
            .second_operand as CelAst.ConstantNode
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

      throw new Error("UnaryNode without operand");
    }

    default:
      throw new Error(`Unsupported node type: ${node.node_type}`);
  }
}
