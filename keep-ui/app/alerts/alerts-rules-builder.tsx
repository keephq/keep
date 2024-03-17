import { FormEventHandler, useMemo, useState } from "react";
import Modal from "components/ui/Modal";
import { Button, Textarea } from "@tremor/react";
import QueryBuilder, {
  Field,
  RuleGroupType,
  defaultValidator,
  formatQuery,
  parseCEL,
} from "react-querybuilder";
import "react-querybuilder/dist/query-builder.scss";
import { Table } from "@tanstack/react-table";
import { AlertDto } from "./models";

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

  const onApplyFilter: FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
  };

  const onGenerateQuery = () => {
    setIsGUIOpen(false);
    setCELRules(formatQuery(query, "cel"));
  };

  const fields: Field[] = table
    .getAllColumns()
    .filter(({ getIsPinned }) => getIsPinned() === false)
    .map(({ id, columnDef }) => ({
      name: id,
      label: columnDef.header as string,
    }));

  return (
    <form
      className="flex flex-col gap-y-2 w-full justify-end"
      onSubmit={onApplyFilter}
    >
      <Modal
        isOpen={isGUIOpen}
        onClose={() => setIsGUIOpen(false)}
        className="w-[50%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
        title="Query Builder"
      >
        <div className="space-y-2 pt-4">
          <QueryBuilder
            query={query}
            fields={fields}
            onQueryChange={(query) => setQuery(query)}
            addRuleToNewGroups
            showCombinatorsBetweenRules={false}
          />
          <div className="inline-flex justify-end">
            <Button color="orange" onClick={onGenerateQuery}>
              Generate Query
            </Button>
          </div>
        </div>
      </Modal>
      <Textarea
        className="max-h-64 min-h-10"
        value={CELRules}
        onValueChange={(value) => setCELRules(value)}
      />
      <div className="flex justify-end gap-x-2">
        <Button
          variant="secondary"
          color="orange"
          type="button"
          onClick={() => {
            setIsGUIOpen(true);

            console.log(defaultValidator(parseCEL(CELRules)));
            setQuery(parseCEL(CELRules));
          }}
        >
          Open GUI view
        </Button>
        <Button className="inline-flex w-auto" color="orange">
          Apply Filter
        </Button>
      </div>
    </form>
  );
};
