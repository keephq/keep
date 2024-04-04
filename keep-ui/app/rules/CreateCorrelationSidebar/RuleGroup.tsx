import { Button } from "@tremor/react";
import {
  RuleGroupType,
  RuleGroupProps as QueryRuleGroupProps,
} from "react-querybuilder";
import { RuleFields } from "./RuleFields";

type RuleGroupProps = {
  query: RuleGroupType;
  queryRuleProps: QueryRuleGroupProps;
};

export const RuleGroup = ({ query, queryRuleProps }: RuleGroupProps) => {
  const { actions, ruleGroup } = queryRuleProps;
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
      {rules.map((rule, groupIndex) =>
        // we only want rule groups to be rendered
        typeof rule === "object" && "combinator" in rule ? (
          <RuleFields
            key={rule.id}
            rule={rule}
            groupIndex={groupIndex}
            onRuleAdd={onRuleAdd}
            onRuleRemove={onRuleRemove}
            query={query}
          />
        ) : null
      )}
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
