import { PlusIcon } from "@radix-ui/react-icons";
import { Badge, Icon } from "@tremor/react";
import { Fragment } from "react";
import { RuleGroupType } from "react-querybuilder";

type FormattedQueryCellProps = {
  query: RuleGroupType;
};

export const FormattedQueryCell = ({ query }: FormattedQueryCellProps) => (
  <div className="inline-flex items-center">
    {query.rules.map((group, groupI) => (
      <Fragment key={groupI}>
        <div className="p-2 bg-gray-50 border rounded space-x-2">
          {"combinator" in group
            ? group.rules.map((rule, ruleI) => (
                <Fragment key={ruleI}>
                  {"field" in rule ? (
                    <span className="space-x-2">
                      <b>{rule.field}</b>{" "}
                      <code className="font-mono">{rule.operator}</code>
                      <Badge color="orange">{rule.value}</Badge>
                    </span>
                  ) : undefined}
                </Fragment>
              ))
            : null}
        </div>
        {query.rules.length !== groupI + 1 && (
          <Icon className="mx-1" icon={PlusIcon} size="sm" color="slate" />
        )}
      </Fragment>
    ))}
  </div>
);
