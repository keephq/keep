import { useState } from "react";
import QueryBuilder, { RuleGroupType } from "react-querybuilder";
import { RuleGroup } from "./RuleGroup";
import "../query-builder.scss";

const DEFAULT_QUERY: RuleGroupType = {
  combinator: "and",
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
};

export const CreateCorrelationGroups = () => {
  const [query, setQuery] = useState<RuleGroupType>(DEFAULT_QUERY);

  const onQueryChange = (query: RuleGroupType) => {
    return setQuery(query);
  };

  return (
    <div>
      <p className="text-tremor-default font-medium text-tremor-content-strong mb-2">
        Add group(s) of conditions
      </p>
      <QueryBuilder
        query={query}
        onQueryChange={onQueryChange}
        addRuleToNewGroups
        controlElements={{
          ruleGroup: (props) => <RuleGroup query={query} actionProps={props} />,
        }}
      />
    </div>
  );
};
