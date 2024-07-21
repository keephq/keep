import { Button } from "@tremor/react";
import { RuleGroupProps as QueryRuleGroupProps } from "react-querybuilder";
import { RuleFields } from "./RuleFields";

export const RuleGroup = ({ actions, ruleGroup }: QueryRuleGroupProps) => {
  const { onRuleAdd, onGroupAdd, onRuleRemove, onPropChange } = actions;
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
            onPropChange={onPropChange}
            query={ruleGroup}
            groupsLength={rules.length}
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
