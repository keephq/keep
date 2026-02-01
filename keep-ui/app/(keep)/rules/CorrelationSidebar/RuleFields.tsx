import { useEffect, useState } from "react";
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
import { CorrelationFormType } from "./types";
import { TIMEFRAME_UNITS_TO_SECONDS } from "./timeframe-constants";
import { useDeduplicationFields } from "@/utils/hooks/useDeduplicationRules";
import { get } from "lodash";
import { useMatchingAlerts } from "./useMatchingAlerts";

const DEFAULT_OPERATORS = defaultOperators.filter((operator) =>
  [
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
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

const OPERATORS_FORCE_TYPE_CAST = {
  ">=": "number",
  "<=": "number",
  "<": "number",
  ">": "number",
};

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

  useEffect(() => {
    setFields(avaliableFields);
  }, [avaliableFields]);

  const onValueChange = (selectedValue: string) => {
    selectedValue = selectedValue || ""; // prevent null values

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

  const castValueToOperationType = (value: string) => {
    const castTo: string = get(
      OPERATORS_FORCE_TYPE_CAST,
      ruleField.operator,
      "text"
    );
    return castTo === "number" ? Number(value) : value;
  };

  return (
    <div key={ruleField.id}>
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0 grid grid-cols-3 gap-2">
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
                onValueChange={(newValue) =>
                  onFieldChange("value", castValueToOperationType(newValue))
                }
                defaultValue={ruleField.value}
                required
                error={!ruleField.value}
                errorMessage={
                  ruleField.value ? undefined : "Rule value is required"
                }
              />
            </div>
          )}
        </div>
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

  const { data: deduplicationFields = {} } = useDeduplicationFields();

  const uniqueDeduplicationFields = Object.values(deduplicationFields)
    .flat()
    .filter(
      (field) => DEFAULT_FIELDS.find((f) => f.name === field) === undefined
    ) // remove duplicates
    .map((field) => ({
      label: field,
      name: field,
      datatype: "text",
    }));

  const availableFields = DEFAULT_FIELDS.concat(
    uniqueDeduplicationFields
  ).filter(({ name }) => selectedFields.includes(name) === false);

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

  const { watch } = useFormContext<CorrelationFormType>();
  const timeframeInSeconds = watch("timeUnit")
    ? TIMEFRAME_UNITS_TO_SECONDS[watch("timeUnit")](+watch("timeAmount"))
    : 0;

  const {
    data: alertsFound = [],
    totalCount: totalAlertsFound,
    isLoading,
  } = useMatchingAlerts({ combinator: "and", rules: ruleFields });

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

        <AlertsFoundBadge
          totalAlertsFound={totalAlertsFound}
          alertsFound={alertsFound}
          isLoading={isLoading}
          role={"ruleCondition"}
        />
      </div>
    </div>
  );
};
