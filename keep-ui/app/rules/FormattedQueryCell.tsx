import { Badge } from "@tremor/react";
import { Fragment } from "react";
import { RuleGroupType } from "react-querybuilder";

type FormattedQueryCellProps = {
  query: RuleGroupType;
};

export const FormattedQueryCell = ({ query }: FormattedQueryCellProps) => (
  <div className="space-x-4">
    {query.rules.map((group, groupI) => (
      <Fragment key={groupI}>
        {"combinator" in group ? (
          <Fragment>
            {group.rules.map((rule, ruleI) => (
              <span key={ruleI} className="p-2 bg-gray-50 border rounded">
                {"field" in rule ? (
                  <span className="space-x-2">
                    <b>{rule.field}</b>{" "}
                    <code className="font-mono">{rule.operator}</code>
                    <Badge color="orange">{rule.value}</Badge>
                  </span>
                ) : undefined}
              </span>
            ))}
          </Fragment>
        ) : null}
      </Fragment>
    ))}
  </div>
);
