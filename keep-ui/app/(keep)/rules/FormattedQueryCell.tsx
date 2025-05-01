import { PlusIcon } from "@radix-ui/react-icons";
import { Badge, Icon } from "@tremor/react";
import { Fragment } from "react";
import { RuleGroupArray, RuleGroupType, RuleType } from "react-querybuilder";
import * as Tooltip from "@radix-ui/react-tooltip";
import { CelAst } from "@/utils/cel-ast";

type FormattedQueryCellProps = {
  query: CelAst.Node;
};

export const FormattedQueryCell = ({ query }: FormattedQueryCellProps) => {
  console.log("ihor", query);
  let displayedRules: any[] = query.rules;
  let rulesInTooltip: any[] = [];

  if (query.rules.length > 2) {
    displayedRules = query.rules.slice(0, 1);
    rulesInTooltip = query.rules.slice(1);
  }

  // tb: this is a patch to make it work, needs refactor
  const anyCombinator = query.rules.some((rule) => "combinator" in rule);

  function renderRules(
    rules: RuleGroupArray<
      RuleGroupType<RuleType<string, string, any, string>, string>,
      RuleType<string, string, any, string>
    >
  ): JSX.Element[] | JSX.Element {
    return anyCombinator ? (
      rules.map((group, groupI) => (
        <Fragment key={groupI}>
          <div className="px-2 py-1 bg-gray-50 border rounded space-x-2">
            {"combinator" in group
              ? group.rules.map((rule, ruleI) => (
                  <Fragment key={ruleI}>
                    {"field" in rule ? (
                      <span className="space-x-2">
                        <b>{rule.field}</b>{" "}
                        <code className="font-mono">{rule.operator}</code>
                        <Badge color="orange" className="px-1 min-w-6">
                          {rule.value}
                        </Badge>
                      </span>
                    ) : undefined}
                  </Fragment>
                ))
              : null}
          </div>
          {rules.length !== groupI + 1 && (
            <Icon icon={PlusIcon} size="xs" color="slate" />
          )}
        </Fragment>
      ))
    ) : (
      <Fragment>
        <div className="p-2 bg-gray-50 border rounded space-x-2">
          {rules.map((rule, ruleI) => {
            return (
              <Fragment key={ruleI}>
                {"field" in rule ? (
                  <span className="space-x-2">
                    <b>{rule.field}</b>{" "}
                    <code className="font-mono">{rule.operator}</code>
                    {rule.value && <Badge color="orange">{rule.value}</Badge>}
                  </span>
                ) : undefined}
              </Fragment>
            );
          })}
        </div>
      </Fragment>
    );
  }

  return (
    <div className="inline-flex items-center">
      {renderRules(displayedRules)}
      {rulesInTooltip.length > 0 && (
        <>
          <Icon icon={PlusIcon} size="xs" color="slate" />
          <Tooltip.Provider>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <span className="font-bold text-xs">
                  {rulesInTooltip.length} more
                </span>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content sideOffset={5}>
                  <div className="bg-white invert-dark-mode dark:bg-gray-50 border-gray-200 p-2 rounded inline-flex items-center">
                    {renderRules(rulesInTooltip)}
                  </div>
                  <Tooltip.Arrow />
                </Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          </Tooltip.Provider>
        </>
      )}
    </div>
  );
};
