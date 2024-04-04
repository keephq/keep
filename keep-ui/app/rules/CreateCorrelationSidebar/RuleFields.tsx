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
  const [isValueEnabled, setIsValueEnabled] = useState(true);

  const onValueChange = (selectedValue: string) => {
    if (searchValue.length) {
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
    }
  };

  const onOperatorSelect = (selectedValue: string) => {
    if (selectedValue === "null" || selectedValue === "notNull") {
      return setIsValueEnabled(false);
    }

    return setIsValueEnabled(true);
  };

  return (
    <div key={ruleField.id}>
      <div className="flex items-center gap-x-2">
        <SearchSelect
          defaultValue={ruleField.field}
          onValueChange={onValueChange}
          onSearchValueChange={setSearchValue}
          enableClear={false}
          name={ruleField.field}
          required
        >
          {fields.map((field) => (
            <SearchSelectItem key={field.name} value={field.name}>
              {field.label}
            </SearchSelectItem>
          ))}
          {searchValue.trim() && (
            <SearchSelectItem value={searchValue}>
              {searchValue}
            </SearchSelectItem>
          )}
        </SearchSelect>
        <Select
          defaultValue={ruleField.operator}
          onValueChange={onOperatorSelect}
          name={ruleField.operator}
          required
        >
          {DEFAULT_OPERATORS.map((operator) => (
            <SelectItem key={operator.name} value={operator.name}>
              {operator.label}
            </SelectItem>
          ))}
        </Select>
        {isValueEnabled && (
          <TextInput
            name={ruleField.value}
            defaultValue={ruleField.value}
            required
          />
        )}
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
  rule: RuleGroupType<RuleType<string, string, any, string>, string>;
  onRuleAdd: QueryActions["onRuleAdd"];
  onRuleRemove: QueryActions["onRuleRemove"];
  groupIndex: number;
  query: RuleGroupType;
};

export const RuleFields = ({
  rule,
  onRuleAdd,
  onRuleRemove,
  groupIndex,
  query,
}: RuleFieldProps) => {
  const { rules: ruleFields } = rule;

  const onAddRuleFieldClick = () => {
    return onRuleAdd(
      { field: "severity", operator: "=", value: "" },
      [groupIndex],
      query
    );
  };

  const onRemoveRuleFieldClick = (removedRuleFieldIndex: number) => {
    // if the rule group fields is down to 1,
    // this field is the last one, so just remove the rule group
    if (ruleFields.length === 1) {
      return onRuleRemove([groupIndex]);
    }

    return onRuleRemove([groupIndex, removedRuleFieldIndex]);
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
};
