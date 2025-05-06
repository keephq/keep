export namespace CelAst {
  export enum LogicalNodeOperator {
    AND = "&&",
    OR = "||",
  }

  export enum ComparisonNodeOperator {
    LT = "<",
    LE = "<=",
    GT = ">",
    GE = ">=",
    EQ = "==",
    NE = "!=",
    IN = "in",
    CONTAINS = "contains",
    STARTS_WITH = "startsWith",
    ENDS_WITH = "endsWith",
  }

  export enum UnaryNodeOperator {
    NOT = "!",
    NEG = "-",
  }

  export enum DataType {
    STRING = "string",
    UUID = "uuid",
    INTEGER = "integer",
    FLOAT = "float",
    DATETIME = "datetime",
    BOOLEAN = "boolean",
    OBJECT = "object",
    ARRAY = "array",
    NULL = "null",
  }

  export interface Node {
    node_type: string;
  }

  export interface ConstantNode extends Node {
    value: any;
  }

  export interface ParenthesisNode extends Node {
    expression: Node;
  }

  export interface LogicalNode extends Node {
    left: Node;
    operator: LogicalNodeOperator;
    right: Node;
  }

  export interface ComparisonNode extends Node {
    first_operand?: Node;
    operator: ComparisonNodeOperator;
    second_operand?: Node | any;
  }

  export interface UnaryNode extends Node {
    operator: UnaryNodeOperator;
    operand?: Node;
  }

  export interface PropertyAccessNode extends Node {
    path: string[];
    value?: any;
    data_type?: DataType;
  }
}
