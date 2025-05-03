import { Fragment, useMemo } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { CorrelationSidebarHeader } from "./CorrelationSidebarHeader";
import { CorrelationSidebarBody } from "./CorrelationSidebarBody";
import { CorrelationFormType } from "./types";
import { Drawer } from "@/shared/ui/Drawer";
import { Rule } from "@/utils/hooks/useRules";
import { DefaultRuleGroupType, parseCEL } from "react-querybuilder";
import { CelAst } from "@/utils/cel-ast";
import { v4 as uuidv4 } from "uuid";

const TIMEFRAME_UNITS_FROM_SECONDS = {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => amount / 60,
  hours: (amount: number) => amount / 3600,
  days: (amount: number) => amount / 86400,
} as const;

export const DEFAULT_CORRELATION_FORM_VALUES: CorrelationFormType = {
  name: "",
  description: "",
  timeAmount: 24,
  timeUnit: "hours",
  groupedAttributes: [],
  requireApprove: false,
  resolveOn: "never",
  createOn: "any",
  incidentNameTemplate: "",
  incidentPrefix: "",
  multiLevel: false,
  multiLevelPropertyName: "",
  query: {
    combinator: "or",
    rules: [
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
    ],
  },
};

type CorrelationSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  selectedRule?: Rule;
  defaultValue?: CorrelationFormType;
};

function visitLogicalNode(node: CelAst.LogicalNode): any[] {}

function celAstToQueryBuilder(node: CelAst.Node): DefaultRuleGroupType {
  switch (node.node_type) {
    case "LogicalNode": {
      const left = celAstToQueryBuilder(
        ((node as CelAst.LogicalNode).left as any).expression ??
          (node as CelAst.LogicalNode).left
      );
      const right = celAstToQueryBuilder(
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
      return celAstToQueryBuilder((node as CelAst.ParenthesisNode).expression);
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

      return {
        field,
        operator,
        value,
        id: uuidv4(),
      } as any;
    }

    default:
      throw new Error(`Unsupported node type: ${node.node_type}`);
  }
}

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

export const CorrelationSidebar = ({
  isOpen,
  toggle,
  selectedRule,
}: CorrelationSidebarProps) => {
  const correlationFormFromRule: CorrelationFormType = useMemo(() => {
    if (selectedRule) {
      let query = parseCEL(selectedRule.definition_cel);
      query.rules;
      console.log("IHor", {
        reactQueryBuilder: JSON.parse(JSON.stringify(query)),
        customConverter: celAstToQueryBuilder(selectedRule.definition_cel_ast),
      });
      query = celAstToQueryBuilder(selectedRule.definition_cel_ast);
      const anyCombinator = query.rules?.some((rule) => "combinator" in rule);

      const queryInGroup: DefaultRuleGroupType = {
        ...query,
        rules: anyCombinator
          ? query.rules
          : [
              {
                combinator: "and",
                rules: query.rules,
              },
            ],
      };

      const timeunit = selectedRule.timeunit ?? "seconds";

      return {
        name: selectedRule.name,
        description: selectedRule.group_description ?? "",
        timeAmount: TIMEFRAME_UNITS_FROM_SECONDS[timeunit](
          selectedRule.timeframe
        ),
        timeUnit: timeunit,
        groupedAttributes: selectedRule.grouping_criteria,
        requireApprove: selectedRule.require_approve,
        resolveOn: selectedRule.resolve_on,
        createOn: selectedRule.create_on,
        query: queryInGroup,
        incidents: selectedRule.incidents,
        incidentNameTemplate: selectedRule.incident_name_template || "",
        incidentPrefix: selectedRule.incident_prefix || "",
        multiLevel: selectedRule.multi_level,
        multiLevelPropertyName: selectedRule.multi_level_property_name || "",
      };
    }

    return DEFAULT_CORRELATION_FORM_VALUES;
  }, [selectedRule]);

  return (
    <Drawer
      isOpen={isOpen}
      onClose={toggle}
      className="fixed right-0 inset-y-0 min-w-12 bg-white p-6 overflow-auto flex flex-col"
    >
      <div className="flex flex-col h-full max-h-full overflow-hidden">
        <CorrelationSidebarHeader toggle={toggle} />
        <CorrelationSidebarBody
          toggle={toggle}
          defaultValue={correlationFormFromRule}
        />
      </div>
    </Drawer>
  );
};


