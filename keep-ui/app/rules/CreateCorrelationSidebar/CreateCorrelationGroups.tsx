import { memo, useState } from "react";
import QueryBuilder, { RuleGroupType } from "react-querybuilder";
import { RuleGroup } from "./RuleGroup";
import "../query-builder.scss";

type CreateCorrelationGroupsProps = {
  query: RuleGroupType;
  onQueryChange: (newQuery: RuleGroupType) => void;
};

export const CreateCorrelationGroups = ({
  query,
  onQueryChange,
}: CreateCorrelationGroupsProps) => {
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
          ruleGroup: RuleGroup,
        }}
      />
    </div>
  );
};
