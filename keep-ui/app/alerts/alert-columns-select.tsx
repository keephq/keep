import { Table } from "@tanstack/table-core";
import { Subtitle, MultiSelect, MultiSelectItem } from "@tremor/react";
import { AlertDto } from "./models";
import Select, { components, ValueContainerProps } from "react-select";
import { staticColumns } from "./alert-table";
import React from "react";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName?: string;
  isLoading: boolean;
}

export interface Option {
  readonly value: string;
  readonly label: string;
  readonly color: string;
  readonly isDisabled?: boolean;
}

const ValueContainer = (props: ValueContainerProps<unknown, boolean>) => {
  const { children, getValue, ...rest } = props;

  var values = getValue();
  var valueLabel = "";

  if (values.length > 0)
    valueLabel += props.selectProps.getOptionLabel(values[0]);
  if (values.length > 1) valueLabel += ` & ${values.length - 1} more`;

  // Keep standard placeholder and input from react-select
  var childsToRender = React.Children.toArray(children).filter(
    (child) =>
      React.isValidElement(child) && // Ensure child is a ReactElement
      ["Input", "DummyInput", "Placeholder"].includes((child.type as any).name)
  );

  return (
    <components.ValueContainer {...props}>
      {!props.selectProps.inputValue && valueLabel}
      {childsToRender}
    </components.ValueContainer>
  );
};

const convertColumnToOption = (column: any) => {
  return {
    label: column.id,
    value: column.id,
  } as Option;
};

export const getHiddenColumnsLocalStorageKey = (
  presetName: string = "default"
) => {
  return `hiddenFields-${presetName}`;
};

export const saveColumns = (presetName: string, columns: string[]) => {
  // This is where visibility is being actually saved
  localStorage.setItem(
    getHiddenColumnsLocalStorageKey(presetName),
    JSON.stringify([...columns, ...staticColumns])
  );
};

export default function AlertColumnsSelect({
  table,
  presetName,
  isLoading,
}: AlertColumnsSelectProps) {
  const columnsOptions = table
    .getAllColumns()
    .filter((c) => staticColumns.includes(c.id) === false)
    .map((c) => c.id);
  const selectedColumns = table
    .getAllColumns()
    .filter(
      (col) => col.getIsVisible() && staticColumns.includes(col.id) === false
    )
    .map((c) => c.id);

  const onChange = (valueKeys: string[]) => {
    const columnsToShow = table
      .getAllColumns()
      .filter((c) => c.getIsVisible() === false && valueKeys.includes(c.id));
    const columnsToHide = table
      .getAllColumns()
      .filter((c) => c.getIsVisible() && !valueKeys.includes(c.id));
    columnsToShow.forEach((c) => c.toggleVisibility(true));
    columnsToHide.forEach((c) => c.toggleVisibility(false));
    if (presetName) saveColumns(presetName, valueKeys);
  };

  return (
    <div className="w-96">
      <Subtitle>Columns</Subtitle>
      <MultiSelect value={selectedColumns} onValueChange={onChange}>
        {columnsOptions.map((column) => (
          <MultiSelectItem key={column} value={column}>
            {column}
          </MultiSelectItem>
        ))}
      </MultiSelect>
      {/* <Select
        isMulti
        isClearable={false}
        value={selectedColumns}
        options={columnsOptions}
        isDisabled={isLoading}
        closeMenuOnSelect={false}
        components={{ ValueContainer: ValueContainer as any }}
        onChange={(value) =>
          // todo (tb): this is a stupid hack to keep the checkbox and alertMenu columns displayed
          onChange(value.map((v) => v.value))
        }
      /> */}
    </div>
  );
}
