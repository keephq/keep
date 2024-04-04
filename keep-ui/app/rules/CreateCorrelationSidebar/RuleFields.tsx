import { useState } from "react";
import {
  Button,
  SearchSelect,
  SearchSelectItem,
  Select,
  SelectItem,
  TextInput,
} from "@tremor/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import {
  RuleGroupType,
  QueryActions,
  RuleType,
  defaultOperators,
  Field,
  RuleGroupTypeAny,
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
  { name: "source", label: "source", datatype: "text" },
  { name: "severity", label: "severity", datatype: "text" },
  { name: "service", label: "service", datatype: "text" },
];

type FieldProps = {
  ruleField: RuleType<string, string, any, string>;
  avaliableFields: Field[];
  onRemoveFieldClick: () => void;
  onFieldChange: (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown
  ) => void;
};

const Field = ({
  ruleField,
  avaliableFields,
  onRemoveFieldClick,
  onFieldChange,
}: FieldProps) => {
  const [fields, setFields] = useState<Field[]>(avaliableFields);

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
        setFields((fields) => [
          ...fields,
          { name: selectedValue, label: selectedValue, datatype: "text" },
        ]);
      }
    }

    onFieldChange("field", selectedValue);
  };

  const onOperatorSelect = (selectedValue: string) => {
    onFieldChange("operator", selectedValue);

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
  onPropChange: QueryActions["onPropChange"];
  groupIndex: number;
  query: RuleGroupTypeAny;
};

export const RuleFields = ({
  rule,
  onRuleAdd,
  onRuleRemove,
  onPropChange,
  groupIndex,
  query,
}: RuleFieldProps) => {
  const { rules: ruleFields } = rule;

  const selectedFields = ruleFields.reduce<string[]>(
    (acc, ruleField) =>
      "field" in ruleField ? acc.concat(ruleField.field) : acc,
    []
  );

  const availableFields = DEFAULT_FIELDS.filter(
    ({ name }) => selectedFields.includes(name) === false
  );

  const onAddRuleFieldClick = () => {
    const nextAvailableField = availableFields.at(0);

    if (nextAvailableField) {
      return onRuleAdd(
        { field: nextAvailableField.name, operator: "=", value: "" },
        [groupIndex],
        query
      );
    }
  };

  const onRemoveRuleFieldClick = (removedRuleFieldIndex: number) => {
    // if the rule group fields is down to 1,
    // this field is the last one, so just remove the rule group
    if (ruleFields.length === 1) {
      return onRuleRemove([groupIndex]);
    }

    return onRuleRemove([groupIndex, removedRuleFieldIndex]);
  };

  const onFieldChange = (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown,
    ruleFieldIndex: number
  ) => {
    return onPropChange(prop, value, [groupIndex, ruleFieldIndex]);
  };

  return (
    <div key={rule.id} className="bg-gray-100 px-4 py-3 rounded space-y-2">
      {ruleFields.map((ruleField, ruleFieldIndex) => {
        if ("field" in ruleField) {
          return (
            <Field
              key={ruleField.id}
              ruleField={ruleField}
              onRemoveFieldClick={() => onRemoveRuleFieldClick(ruleFieldIndex)}
              // add the rule field as an available selection
              avaliableFields={availableFields.concat({
                label: ruleField.field,
                name: ruleField.field,
              })}
              onFieldChange={(prop, value) =>
                onFieldChange(prop, value, ruleFieldIndex)
              }
            />
          );
        }

        return null;
      })}
      <Button
        onClick={onAddRuleFieldClick}
        type="button"
        variant="light"
        color="orange"
        disabled={availableFields.length === 0}
      >
        Add condition
      </Button>
    </div>
  );
};
