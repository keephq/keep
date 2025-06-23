import { convertCelAstToQueryBuilderAst } from "./convert-cel-ast-to-query-builder-ast.function";
import { CelAst } from "@/utils/cel-ast";

describe("convertCelAstToQueryBuilderAst", () => {
  it("should convert a LogicalNode with AND operator", () => {
    const logicalNode: CelAst.LogicalNode = {
      node_type: "LogicalNode",
      operator: CelAst.LogicalNodeOperator.AND,
      left: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.EQ,
        second_operand: { value: "value1" },
      } as CelAst.ComparisonNode,
      right: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field2"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.NE,
        second_operand: { value: "value2" },
      } as CelAst.ComparisonNode,
    };

    const result = convertCelAstToQueryBuilderAst(logicalNode);

    expect(result).toEqual({
      combinator: "and",
      rules: [
        {
          field: "field1",
          operator: "=",
          value: "value1",
          id: expect.any(String),
        },
        {
          field: "field2",
          operator: "!=",
          value: "value2",
          id: expect.any(String),
        },
      ],
    });
  });

  it("should convert a LogicalNode with OR operator", () => {
    const logicalNode: CelAst.LogicalNode = {
      node_type: "LogicalNode",
      operator: CelAst.LogicalNodeOperator.OR,
      left: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.GT,
        second_operand: { value: 10 },
      } as CelAst.ComparisonNode,
      right: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field2"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.LT,
        second_operand: { value: 20 },
      } as CelAst.ComparisonNode,
    };

    const result = convertCelAstToQueryBuilderAst(logicalNode);

    expect(result).toEqual({
      combinator: "or",
      rules: [
        {
          combinator: "and",
          rules: [
            {
              field: "field1",
              operator: ">",
              value: 10,
              id: expect.any(String),
            },
          ],
        },
        {
          combinator: "and",
          rules: [
            {
              field: "field2",
              operator: "<",
              value: 20,
              id: expect.any(String),
            },
          ],
        },
      ],
    });
  });

  it("should convert a LogicalNode with OR operator containing LogicalNode with AND operator", () => {
    const logicalNode: CelAst.LogicalNode = {
      node_type: "LogicalNode",
      operator: CelAst.LogicalNodeOperator.OR,
      left: {
        node_type: "LogicalNode",
        left: {
          node_type: "ComparisonNode",
          first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
          operator: CelAst.ComparisonNodeOperator.GT,
          second_operand: { value: 10 },
        } as CelAst.ComparisonNode,
        operator: CelAst.LogicalNodeOperator.AND,
        right: {
          node_type: "ComparisonNode",
          first_operand: { path: ["field2"] } as CelAst.PropertyAccessNode,
          operator: CelAst.ComparisonNodeOperator.LE,
          second_operand: { value: 10 },
        } as CelAst.ComparisonNode,
      } as CelAst.LogicalNode,
      right: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field3"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.LT,
        second_operand: { value: 20 },
      } as CelAst.ComparisonNode,
    };

    const result = convertCelAstToQueryBuilderAst(logicalNode);

    expect(result).toEqual({
      combinator: "or",
      rules: [
        {
          combinator: "and",
          rules: [
            {
              field: "field1",
              operator: ">",
              value: 10,
              id: expect.any(String),
            },
            {
              field: "field2",
              operator: "<=",
              value: 10,
              id: expect.any(String),
            },
          ],
        },
        {
          combinator: "and",
          rules: [
            {
              field: "field3",
              operator: "<",
              value: 20,
              id: expect.any(String),
            },
          ],
        },
      ],
    });
  });

  it("should convert a ComparisonNode with EQ operator and null value to 'null' operator", () => {
    const comparisonNode: CelAst.ComparisonNode = {
      node_type: "ComparisonNode",
      first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
      operator: CelAst.ComparisonNodeOperator.EQ,
      second_operand: { value: null },
    };

    const result = convertCelAstToQueryBuilderAst(comparisonNode);

    expect(result).toEqual({
      combinator: "and",
      rules: [
        {
          field: "field1",
          operator: "null",
          id: expect.any(String),
        },
      ],
    });
  });

  it.each([
    [CelAst.ComparisonNodeOperator.EQ, "="],
    [CelAst.ComparisonNodeOperator.NE, "!="],
    [CelAst.ComparisonNodeOperator.CONTAINS, "contains"],
    [CelAst.ComparisonNodeOperator.STARTS_WITH, "beginsWith"],
    [CelAst.ComparisonNodeOperator.ENDS_WITH, "endsWith"],
  ])(
    "should convert %s operator to %s",
    (celOperator, queryBuilderOperator) => {
      const comparisonNode: CelAst.ComparisonNode = {
        node_type: "ComparisonNode",
        first_operand: {
          path: ["field1", "field2"],
        } as CelAst.PropertyAccessNode,
        operator: celOperator,
        second_operand: { value: "testValue" },
      };

      const result = convertCelAstToQueryBuilderAst(comparisonNode);

      expect(result).toEqual({
        combinator: "and",
        rules: [
          {
            field: "field1.field2",
            operator: queryBuilderOperator,
            value: "testValue",
            id: expect.any(String),
          },
        ],
      });
    }
  );

  it("should convert a ComparisonNode with NE operator and null value to 'notNull' operator", () => {
    const comparisonNode: CelAst.ComparisonNode = {
      node_type: "ComparisonNode",
      first_operand: {
        path: ["field1", "field2"],
      } as CelAst.PropertyAccessNode,
      operator: CelAst.ComparisonNodeOperator.NE,
      second_operand: { value: null },
    };

    const result = convertCelAstToQueryBuilderAst(comparisonNode);

    expect(result).toEqual({
      combinator: "and",
      rules: [
        {
          field: "field1.field2",
          operator: "notNull",
          id: expect.any(String),
        },
      ],
    });
  });

  it("should convert a UnaryNode with NOT IN operator to notIn opearator", () => {
    const unaryNode: CelAst.UnaryNode = {
      node_type: "UnaryNode",
      operator: CelAst.UnaryNodeOperator.NOT,
      operand: {
        node_type: "ComparisonNode",
        first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
        operator: CelAst.ComparisonNodeOperator.IN,
        second_operand: { value: [1, 2, 3] },
      } as CelAst.ComparisonNode,
    };

    const result = convertCelAstToQueryBuilderAst(unaryNode);

    expect(result).toEqual({
      combinator: "and",
      rules: [
        {
          field: "field1",
          operator: "notIn",
          value: [1, 2, 3],
          id: expect.any(String),
        },
      ],
    });
  });

  it.each([
    [CelAst.ComparisonNodeOperator.CONTAINS, "doesNotContain"],
    [CelAst.ComparisonNodeOperator.STARTS_WITH, "doesNotBeginWith"],
    [CelAst.ComparisonNodeOperator.ENDS_WITH, "doesNotEndWith"],
  ])(
    "should convert unary not with %s operator to %s operator",
    (celOperator, queryBuilderOperator) => {
      const unaryNode: CelAst.UnaryNode = {
        node_type: "UnaryNode",
        operator: CelAst.UnaryNodeOperator.NOT,
        operand: {
          node_type: "ComparisonNode",
          first_operand: { path: ["field1"] } as CelAst.PropertyAccessNode,
          operator: celOperator,
          second_operand: { value: "testValue" },
        } as CelAst.ComparisonNode,
      };

      const result = convertCelAstToQueryBuilderAst(unaryNode);

      expect(result).toEqual({
        combinator: "and",
        rules: [
          {
            field: "field1",
            operator: queryBuilderOperator,
            value: "testValue",
            id: expect.any(String),
          },
        ],
      });
    }
  );

  it("should throw an error for unsupported node type", () => {
    const unsupportedNode: any = {
      node_type: "UnsupportedNode",
    };

    expect(() => convertCelAstToQueryBuilderAst(unsupportedNode)).toThrow(
      "Unsupported node type: UnsupportedNode"
    );
  });
});
