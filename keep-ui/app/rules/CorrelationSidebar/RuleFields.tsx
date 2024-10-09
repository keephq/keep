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
  Field as QueryField,
  RuleGroupTypeAny,
} from "react-querybuilder";
import { AlertsFoundBadge } from "./AlertsFoundBadge";
import { useFormContext } from "react-hook-form";
import { CorrelationForm } from ".";
import { TIMEFRAME_UNITS_TO_SECONDS } from "./CorrelationSidebarBody";
import { useSearchAlerts } from "utils/hooks/useSearchAlerts";

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

const DEFAULT_FIELDS: QueryField[] = [
  { name: "source", label: "source", datatype: "text" },
  { name: "severity", label: "severity", datatype: "text" },
  { name: "service", label: "service", datatype: "text" },
];

type FieldProps = {
  ruleField: RuleType<string, string, any, string>;
  avaliableFields: QueryField[];
  onRemoveFieldClick: () => void;
  onFieldChange: (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown
  ) => void;
  isInputRemovalDisabled: boolean;
};

const Field = ({
  ruleField,
  avaliableFields,
  onRemoveFieldClick,
  onFieldChange,
  isInputRemovalDisabled,
}: FieldProps) => {
  const [fields, setFields] = useState<QueryField[]>(avaliableFields);

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
      <div className="flex items-start gap-x-2">
        <SearchSelect
          defaultValue={ruleField.field}
          onValueChange={onValueChange}
          onSearchValueChange={setSearchValue}
          enableClear={false}
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
          className="[&_ul]:max-h-96"
          defaultValue={ruleField.operator}
          onValueChange={onOperatorSelect}
          required
        >
          {DEFAULT_OPERATORS.map((operator) => (
            <SelectItem key={operator.name} value={operator.name}>
              {operator.label}
            </SelectItem>
          ))}
        </Select>
        {isValueEnabled && (
          <div>
            <TextInput
              onValueChange={(newValue) => onFieldChange("value", newValue)}
              defaultValue={ruleField.value}
              required
              error={!ruleField.value}
              errorMessage={
                ruleField.value ? undefined : "Rule value is required"
              }
            />
          </div>
        )}

        <Button
          className="mt-2"
          onClick={onRemoveFieldClick}
          size="lg"
          color="red"
          icon={XMarkIcon}
          variant="light"
          type="button"
          disabled={isInputRemovalDisabled}
          title={
            isInputRemovalDisabled
              ? "You must have at least two groups"
              : undefined
          }
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
  groupsLength: number;
};

export const RuleFields = ({
  rule,
  onRuleAdd,
  onRuleRemove,
  onPropChange,
  groupIndex,
  query,
  groupsLength,
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
    // prevent users from removing group if there are only two remaining
    if (groupsLength === 1 && ruleFields.length < 2) {
      return undefined;
    }

    // if the rule group fields is down to 1,
    // this field is the last one, so just remove the rule group
    if (ruleFields.length === 1) {
      return onRuleRemove([groupIndex]);
    }

    return onRuleRemove([groupIndex, removedRuleFieldIndex]);
  };

  const onRemoveGroupClick = () => {
    if (groupsLength > 1) {
      return onRuleRemove([groupIndex]);
    }
  };

  const onFieldChange = (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown,
    ruleFieldIndex: number
  ) => {
    return onPropChange(prop, value, [groupIndex, ruleFieldIndex]);
  };

  const { watch } = useFormContext<CorrelationForm>();
  const timeframeInSeconds = watch("timeUnit")
    ? TIMEFRAME_UNITS_TO_SECONDS[watch("timeUnit")](+watch("timeAmount"))
    : 0;

  const { data: alertsFound = [], isLoading } = useSearchAlerts({
    query: { combinator: "and", rules: ruleFields },
    timeframe: timeframeInSeconds,
  });

  return (
    <div key={rule.id} className="bg-gray-100 px-4 py-3 rounded space-y-2">
      {ruleFields.map((ruleField, ruleFieldIndex) => {
        if ("field" in ruleField) {
          const isInputRemovalDisabled =
            // groups length is only 2
            groupsLength === 1 && ruleFields.length < 2;

          return (
            <div key={ruleFieldIndex}>
              <div className="mb-2">{ruleFieldIndex > 0 ? "AND" : ""}</div>

              <Field
                ruleField={ruleField}
                key={ruleField.id}
                onRemoveFieldClick={() =>
                  onRemoveRuleFieldClick(ruleFieldIndex)
                }
                // add the rule field as an available selection
                avaliableFields={availableFields.concat({
                  label: ruleField.field,
                  name: ruleField.field,
                })}
                onFieldChange={(prop, value) =>
                  onFieldChange(prop, value, ruleFieldIndex)
                }
                isInputRemovalDisabled={isInputRemovalDisabled}
              />
            </div>
          );
        }

        return null;
      })}

      <div className="flex flex-col">
        <div className="flex justify-between items-center">
          <Button
            onClick={onAddRuleFieldClick}
            type="button"
            variant="light"
            color="orange"
            disabled={availableFields.length === 0}
          >
            Add condition
          </Button>

          <Button
            type="button"
            variant="light"
            color="red"
            title={
              groupsLength <= 1 ? "You must have at least one group" : undefined
            }
            disabled={groupsLength <= 1}
            onClick={onRemoveGroupClick}
          >
            Remove group
          </Button>
        </div>

        <AlertsFoundBadge alertsFound={alertsFound} isLoading={isLoading} />
      </div>
    </div>
  );
};
