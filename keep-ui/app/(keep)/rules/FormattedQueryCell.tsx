import { PlusIcon } from "@radix-ui/react-icons";
import { Badge, Icon } from "@tremor/react";
import { Fragment } from "react";
import { RuleGroupType } from "react-querybuilder";

type FormattedQueryCellProps = {
  query: RuleGroupType;
};

export const FormattedQueryCell = ({ query }: FormattedQueryCellProps) => {
  // tb: this is a patch to make it work, needs refactor
  const anyCombinator = query.rules.some((rule) => "combinator" in rule);

  return (
    <div className="inline-flex items-center">
      {anyCombinator ? (
        query.rules.map((group, groupI) => (
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
        ))
      ) : (
        <Fragment>
          <div className="p-2 bg-gray-50 border rounded space-x-2">
            {query.rules.map((rule, ruleI) => {
              return (
                <Fragment key={ruleI}>
                  {"field" in rule ? (
                    <span className="space-x-2">
                      <b>{rule.field}</b>{" "}
                      <code className="font-mono">{rule.operator}</code>
                      <Badge color="orange">{rule.value}</Badge>
                    </span>
                  ) : undefined}
                </Fragment>
              );
            })}
          </div>
        </Fragment>
      )}
    </div>
  );
};
