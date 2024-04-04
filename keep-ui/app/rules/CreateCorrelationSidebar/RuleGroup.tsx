import { Button } from "@tremor/react";
import {
  RuleGroupType,
  RuleGroupProps as QueryRuleGroupProps,
} from "react-querybuilder";
import { RuleFields } from "./RuleFields";

type RuleGroupProps = {
  query: RuleGroupType;
  actionProps: QueryRuleGroupProps;
};

export const RuleGroup = ({ query, actionProps }: RuleGroupProps) => {
  const { actions, ruleGroup } = actionProps;

  const { onRuleAdd, onGroupAdd, onRuleRemove } = actions;
  const { rules } = ruleGroup;

  const onAddGroupClick = () => {
    return onGroupAdd(
      {
        combinator: "and",
        rules: [{ field: "severity", operator: "=", value: "" }],
      },
      []
    );
  };

  return (
    <div className="space-y-2">
      {rules.map((rule, ruleIndex) => (
        <RuleFields
          key={typeof rule === "string" ? ruleIndex : rule.id}
          rule={rule}
          ruleIndex={ruleIndex}
          onRuleAdd={onRuleAdd}
          onRuleRemove={onRuleRemove}
          query={query}
        />
      ))}
      <Button
        className="mt-3"
        onClick={onAddGroupClick}
        type="button"
        variant="light"
        color="orange"
      >
        Add group
      </Button>
    </div>
  );
};
