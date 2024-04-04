import { useState } from "react";
import QueryBuilder, { Field, RuleGroupType } from "react-querybuilder";
import "../query-builder.scss";
import { RuleGroup } from "./RuleGroup";

const DEFAULT_QUERY: RuleGroupType = {
  combinator: "and",
  rules: [
    {
      combinator: "and",
      rules: [
        { field: "source", operator: "=", value: "" },
        { field: "source", operator: "=", value: "" },
      ],
    },
    {
      combinator: "and",
      rules: [{ field: "source", operator: "=", value: "" }],
    },
  ],
};

const DEFAULT_FIELDS = [
  { name: "source", label: "source", datatype: "text" },
  { name: "severity", label: "severity", datatype: "text" },
  { name: "service", label: "service", datatype: "text" },
];

export const CreateCorrelationGroups = () => {
  const [query, setQuery] = useState<RuleGroupType>(DEFAULT_QUERY);
  const [fields, setFields] = useState<Field[]>(DEFAULT_FIELDS);

  const onQueryChange = (query: RuleGroupType) => {
    return setQuery(query);
  };

  return (
    <div className="overflow-auto">
      <p className="text-tremor-default font-medium text-tremor-content-strong mb-2">
        Add group(s) of conditions
      </p>
      <QueryBuilder
        query={query}
        onQueryChange={onQueryChange}
        fields={fields}
        addRuleToNewGroups
        controlElements={{
          ruleGroup: (props) => <RuleGroup query={query} actionProps={props} />,
        }}
      />
    </div>
  );
};
