import { XMarkIcon } from "@heroicons/react/24/outline";
import {
  Button,
  SearchSelect,
  SearchSelectItem,
  Select,
  SelectItem,
  TextInput,
} from "@tremor/react";
import { useState } from "react";
import {
  RuleGroupType,
  RuleGroupTypeAny,
  QueryActions,
  RuleType,
  defaultOperators,
  Field,
} from "react-querybuilder";

const DEFAULT_OPERATORS = defaultOperators.filter((operator) =>
  [
    "=",
    "contains",
    "beginsWith",
    "endsWith",
    "doesNotContain",
    "doesNotBeginWith",
    "doesNotEndWith",
    "null",
    "notNull",
    "in",
    "notIn",
  ].includes(operator.name)
);

const DEFAULT_FIELDS: Field[] = [
  { name: "source", label: "Source", datatype: "text" },
  { name: "severity", label: "Severity", datatype: "text" },
  { name: "service", label: "Service", datatype: "text" },
];

type FieldProps = {
  ruleField: RuleType<string, string, any, string>;
  onRemoveFieldClick: () => void;
};

const Field = ({ ruleField, onRemoveFieldClick }: FieldProps) => {
  const [fields, setFields] = useState<Field[]>(DEFAULT_FIELDS);
  const [searchValue, setSearchValue] = useState("");

  const onValueChange = (selectedValue: string) => {
    const doesSearchedValueExistInFields = fields.some(
      ({ name }) =>
        name.toLowerCase().trim() === selectedValue.toLowerCase().trim()
    );

    if (doesSearchedValueExistInFields === false) {
      setSearchValue("");
      return setFields((fields) => [
        ...fields,
        { name: selectedValue, label: selectedValue, datatype: "text" },
      ]);
    }
  };

  return (
    <div key={ruleField.id}>
      <div className="flex items-center gap-x-2">
        <SearchSelect
          defaultValue={ruleField.field}
          onValueChange={onValueChange}
          onSearchValueChange={setSearchValue}
          enableClear={false}
        >
          {fields.map((field) => (
            <SearchSelectItem key={field.name} value={field.name}>
              {field.label}
            </SearchSelectItem>
          ))}
          {searchValue && (
            <SearchSelectItem value={searchValue}>
              {searchValue}
            </SearchSelectItem>
          )}
        </SearchSelect>
        <Select defaultValue={ruleField.operator}>
          {DEFAULT_OPERATORS.map((operator) => (
            <SelectItem key={operator.name} value={operator.name}>
              {operator.label}
            </SelectItem>
          ))}
        </Select>
        <TextInput defaultValue={ruleField.value} />
        <Button
          onClick={onRemoveFieldClick}
          size="lg"
          color="red"
          icon={XMarkIcon}
          variant="light"
          type="button"
        />
      </div>
    </div>
  );
};

type RuleFieldProps = {
  rule: RuleGroupTypeAny["rules"][number];
  onRuleAdd: QueryActions["onRuleAdd"];
  onRuleRemove: QueryActions["onRuleRemove"];
  ruleIndex: number;
  query: RuleGroupType;
};

export const RuleFields = ({
  rule,
  onRuleAdd,
  onRuleRemove,
  ruleIndex,
  query,
}: RuleFieldProps) => {
  if (typeof rule === "string") {
    return null;
  }

  if ("combinator" in rule) {
    const { rules: ruleFields } = rule;

    const onAddRuleFieldClick = () => {
      return onRuleAdd(
        { field: "severity", operator: "=", value: "" },
        [ruleIndex],
        query
      );
    };

    const onRemoveRuleFieldClick = (removedRuleFieldIndex: number) => {
      // if the rule group fields is down to 1,
      // this field is the last one, so just remove the rule group
      if (ruleFields.length === 1) {
        return onRuleRemove([ruleIndex]);
      }

      return onRuleRemove([ruleIndex, removedRuleFieldIndex]);
    };

    return (
      <div key={rule.id} className="bg-gray-100 px-4 py-3 rounded space-y-2">
        {ruleFields.map((ruleField, ruleFieldIndex) =>
          "field" in ruleField ? (
            <Field
              key={ruleField.id}
              ruleField={ruleField}
              onRemoveFieldClick={() => onRemoveRuleFieldClick(ruleFieldIndex)}
            />
          ) : null
        )}
        <Button
          onClick={onAddRuleFieldClick}
          type="button"
          variant="light"
          color="orange"
        >
          Add condition
        </Button>
      </div>
    );
  }

  return null;
};
