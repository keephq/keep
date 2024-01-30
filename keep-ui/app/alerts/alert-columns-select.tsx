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
    </div>
  );
}
