import { useState } from "react";
import Modal from "components/ui/Modal";
import { Button, Textarea } from "@tremor/react";
import QueryBuilder, {
  Field,
  RuleGroupType,
  formatQuery,
  parseCEL,
} from "react-querybuilder";
import "react-querybuilder/dist/query-builder.scss";
import { Table } from "@tanstack/react-table";
import { AlertDto } from "./models";

// Culled from: https://stackoverflow.com/a/54372020/12627235
const getAllMatches = (pattern: RegExp, string: string) =>
  // make sure string is a String, and make sure pattern has the /g flag
  String(string).match(new RegExp(pattern, "g"));

// this pattern is far from robust
const variablePattern = /[a-zA-Z$_][0-9a-zA-Z$_]*/;

export const evalWithContext = (context: AlertDto, expression: string) => {
  const variables = getAllMatches(variablePattern, expression) ?? [];

  const func = new Function(...variables, `return (${expression})`);

  const args = variables.map((arg) =>
    Object.hasOwnProperty.call(context, arg)
      ? context[arg as keyof AlertDto]
      : undefined
  );

  return func(...args);
};

type AlertsRulesBuilderProps = {
  table: Table<AlertDto>;
};

export const AlertsRulesBuilder = ({ table }: AlertsRulesBuilderProps) => {
  const [isGUIOpen, setIsGUIOpen] = useState(false);
  const [CELRules, setCELRules] = useState("");
  const [query, setQuery] = useState<RuleGroupType>({
    combinator: "and",
    rules: [],
  });

  const parcedCELRulesToQuery = parseCEL(CELRules);
  const isValidCEL = formatQuery(parcedCELRulesToQuery, "cel") === CELRules;

  const onApplyFilter = () => {
    if (CELRules.length === 0) {
      return table.setGlobalFilter({});
    }

    if (!isValidCEL) {
      alert("Your CEL string is invalid");
    }

    table.setGlobalFilter(CELRules);
  };

  const onGenerateQuery = () => {
    setCELRules(formatQuery(query, "cel"));
    setIsGUIOpen(false);
  };

  const onGUIView = () => {
    if (CELRules.length && !isValidCEL) {
      const isConfirmed = confirm(
        "Your CEL string is invalid. Some conditions might not be displayed. Are you sure you want to generate the query rules?"
      );

      if (!isConfirmed) {
        return;
      }
    }

    setIsGUIOpen(true);
    setQuery(parcedCELRulesToQuery);
  };

  const fields: Field[] = table
    .getAllColumns()
    .filter(({ getIsPinned }) => getIsPinned() === false)
    .map(({ id, columnDef }) => ({
      name: id,
      label: columnDef.header as string,
    }));

  return (
    <div className="flex flex-col gap-y-2 w-full justify-end">
      <Modal
        isOpen={isGUIOpen}
        onClose={() => setIsGUIOpen(false)}
        className="w-[50%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
        title="Query Builder"
      >
        <div className="space-y-2 pt-4">
          <div className="max-h-96 overflow-auto">
            <QueryBuilder
              fields={fields}
              addRuleToNewGroups
              showCombinatorsBetweenRules={false}
            />
          </div>
          <div className="inline-flex justify-end">
            <Button
              color="orange"
              onClick={onGenerateQuery}
              disabled={!query.rules.length}
            >
              Generate Query
            </Button>
          </div>
        </div>
      </Modal>
      <Textarea
        className="max-h-64 min-h-10"
        value={CELRules}
        onValueChange={(newValue) => setCELRules(newValue)}
      />
      <div className="flex justify-end gap-x-2">
        <Button
          variant="secondary"
          color="orange"
          type="button"
          onClick={onGUIView}
        >
          Open GUI view
        </Button>
        <Button
          className="inline-flex w-auto"
          color="orange"
          onClick={onApplyFilter}
        >
          Apply Filter
        </Button>
      </div>
    </div>
  );
};
