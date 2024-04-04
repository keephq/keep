import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Select, SelectItem } from "@tremor/react";
import {
  RuleGroupType,
  RuleGroupTypeAny,
  QueryActions,
} from "react-querybuilder";

type RuleProps = {
  rule: RuleGroupTypeAny["rules"][number];
  onRuleAdd: QueryActions["onRuleAdd"];
  onRuleRemove: QueryActions["onRuleRemove"];
  ruleIndex: number;
  query: RuleGroupType;
};

export const RuleFields = ({
  rule,
  onRuleAdd,
  onRuleRemove,
  ruleIndex,
  query,
}: RuleProps) => {
  if (typeof rule === "string") {
    return null;
  }

  if ("combinator" in rule) {
    const { rules: fields } = rule;

    const onAddRuleClick = () => {
      return onRuleAdd(
        { field: "severity", operator: "=", value: "" },
        [ruleIndex],
        query
      );
    };

    const onRemoveRuleClick = (removedRuleIndex: number) => {
      // if the rule group fields is down to 1,
      // this field is the last one, so just remove the rule group
      if (fields.length === 1) {
        return onRuleRemove([ruleIndex]);
      }

      return onRuleRemove([ruleIndex, removedRuleIndex]);
    };

    return (
      <div key={rule.id} className="bg-gray-100 px-4 py-3 rounded space-y-2">
        {fields.map((rule, fieldIndex) =>
          "field" in rule ? (
            <div key={rule.id}>
              <div className="flex items-center gap-x-2">
                <Select defaultValue={rule.field}>
                  <SelectItem value="source">Source</SelectItem>
                </Select>
                <Select defaultValue={rule.operator}>
                  <SelectItem value={rule.operator}>=</SelectItem>
                </Select>
                <Select defaultValue={rule.value}>
                  <SelectItem value={rule.value}>Hello world</SelectItem>
                </Select>
                <Button
                  onClick={() => onRemoveRuleClick(fieldIndex)}
                  size="lg"
                  color="red"
                  icon={XMarkIcon}
                  variant="light"
                  type="button"
                />
              </div>
            </div>
          ) : null
        )}
        <Button
          onClick={onAddRuleClick}
          type="button"
          variant="light"
          color="orange"
        >
          Add condition
        </Button>
      </div>
    );
  }

  return null;
};
