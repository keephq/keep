import { useEffect, useRef, useState } from "react";
import Modal from "components/ui/Modal";
import { Button, Textarea, Badge } from "@tremor/react";
import QueryBuilder, {
  Field,
  Operator,
  RuleGroupType,
  defaultOperators,
  formatQuery,
  parseCEL,
  parseSQL,
} from "react-querybuilder";
import "react-querybuilder/dist/query-builder.scss";
import { Table } from "@tanstack/react-table";
import { AlertDto } from "./models";
import { format } from "path";

// Culled from: https://stackoverflow.com/a/54372020/12627235
const getAllMatches = (pattern: RegExp, string: string) =>
  // make sure string is a String, and make sure pattern has the /g flag
  String(string).match(new RegExp(pattern, "g"));

const sanitizeCELIntoJS = (celExpression: string) => {
  // "contains" is not a valid JS function
  return celExpression.replace("contains", "includes");
};

// this pattern is far from robust
const variablePattern = /[a-zA-Z$_][0-9a-zA-Z$_]*/;

export const evalWithContext = (context: AlertDto, celExpression: string) => {
  try {
    if (celExpression.length === 0) {
      return new Function();
    }

    const variables = getAllMatches(variablePattern, celExpression) ?? [];
    const jsExpression = sanitizeCELIntoJS(celExpression);

    const func = new Function(...variables, `return (${jsExpression})`);

    const args = variables.map((arg) =>
      Object.hasOwnProperty.call(context, arg)
        ? context[arg as keyof AlertDto]
        : undefined
    );

    return func(...args);
  } catch (error) {
    return;
  }
};

const getOperators = (id: string): Operator[] => {
  if (id === "source") {
    return [
      { name: "contains", label: "contains" },
      { name: "null", label: "null" },
    ];
  }

  return defaultOperators;
};

type AlertsRulesBuilderProps = {
  table: Table<AlertDto>;
  defaultQuery: string | undefined;
};

export const AlertsRulesBuilder = ({
  table,
  defaultQuery = "",
}: AlertsRulesBuilderProps) => {
  const [isGUIOpen, setIsGUIOpen] = useState(false);
  const [isImportSQLOpen, setImportSQLOpen] = useState(false);
  const [sqlQuery, setSQLQuery] = useState(`SELECT *
FROM alerts
WHERE severity = 'critical' and status = 'firing'`);
  const [celRules, setCELRules] = useState(defaultQuery);

  const parcedCELRulesToQuery = parseCEL(celRules);
  const [query, setQuery] = useState<RuleGroupType>(parcedCELRulesToQuery);

  const isValidCEL = formatQuery(parcedCELRulesToQuery, "cel") === celRules;
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  // Adjust the height of the textarea based on its content
  const adjustTextAreaHeight = () => {
    const textArea = textAreaRef.current;
    if (textArea) {
      textArea.style.height = 'auto';
      textArea.style.height = `${textArea.scrollHeight}px`;
    }
  };
  // Adjust the height whenever the content changes
  useEffect(() => {
    adjustTextAreaHeight();
  }, [celRules]);


  useEffect(() => {
    if (isValidCEL) {
      return table.setGlobalFilter(celRules);
    }
  }, [isValidCEL, table, celRules]);

  const onApplyFilter = () => {
    if (celRules.length === 0) {
      return table.resetGlobalFilter();
    }

    return table.setGlobalFilter(celRules);
  };

  const onGenerateQuery = () => {
    setCELRules(formatQuery(query, "cel"));
    setIsGUIOpen(false);
  };

  const onGUIView = () => {
    if (celRules.length && !isValidCEL) {
      const isConfirmed = confirm(
        "Your CEL string is invalid. Some rules might be lost. Are you sure you want to generate the query rules?"
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
      operators: getOperators(id),
    }));

  const onImportSQL = () => {
    setImportSQLOpen(true);
  }

  const convertSQLToCEL = (sql: string): string => {
      const query = parseSQL(sql);
      return formatQuery(query, "cel");
  };

  const onImportSQLSubmit = () => {
    const convertedCEL = convertSQLToCEL(sqlQuery);
    setCELRules(convertedCEL); // Set the converted CEL as the new CEL rules
    setImportSQLOpen(false); // Close the modal
  };


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
              query={query}
              onQueryChange={(newQuery) => setQuery(newQuery)}
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
      <Modal
        isOpen={isImportSQLOpen}
        onClose={() => setImportSQLOpen(false)}
        title="Import from SQL"
      >
        <div className="space-y-4 p-4">
          <Textarea
            className="min-h-[8em] h-auto" // This sets a minimum height and allows it to auto-adjust
            value={sqlQuery}
            onValueChange={setSQLQuery}
            placeholder={sqlQuery}
          />
          <Button color="orange" onClick={onImportSQLSubmit}>
            Convert to CEL
          </Button>
        </div>
      </Modal>
      <div className="flex items-center space-x-2">
        <Badge key={"cel"} size="md" color="orange">
          CEL
        </Badge>
        <Textarea
          ref={textAreaRef}
          className="resize-none overflow-hidden" // Add additional styling if needed
          value={celRules}
          onValueChange={setCELRules}
          placeholder='Use CEL to filter your alerts e.g. source.contains("kibana")'
        />
      </div>
      <div className="flex justify-end gap-x-2">
        <Button
          variant="secondary"
          color="orange"
          type="button"
          onClick={onGUIView}
        >
          Build Query
        </Button>
        <Button
          variant="secondary"
          color="orange"
          type="button"
          onClick={onImportSQL}
        >
          Import from SQL
        </Button>
        <Button
          className="inline-flex w-auto"
          color="orange"
          onClick={onApplyFilter}
        >
          Apply filter
        </Button>
      </div>
    </div>
  );
};
