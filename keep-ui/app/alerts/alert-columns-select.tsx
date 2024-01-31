import { Table } from "@tanstack/table-core";
import { Subtitle, MultiSelect, MultiSelectItem } from "@tremor/react";
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState } from "@tanstack/react-table";
import { getDefaultColumnVisibilityState } from "./alert-table-utils";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName?: string;
  isLoading: boolean;
}

export default function AlertColumnsSelect({
  table,
  presetName,
}: AlertColumnsSelectProps) {
  const tableColumns = table.getAllColumns();

  const [columnVisibility, setColumnVisibility] =
    useLocalStorage<VisibilityState>(
      `column-visibility-${presetName}`,
      getDefaultColumnVisibilityState(tableColumns)
    );

  const columnsOptions = tableColumns
    .filter((col) => col.getIsPinned() === false)
    .map((col) => col.id);

  const selectedColumns = tableColumns
    .filter((col) => col.getIsVisible() && col.getIsPinned() === false)
    .map((col) => col.id);

  const onChange = (valueKeys: string[]) => {
    const newColumnVisibility = columnsOptions.reduce<VisibilityState>(
      (acc, key) => {
        if (valueKeys.includes(key)) {
          return { ...acc, [key]: true };
        }

        return { ...acc, [key]: false };
      },
      columnVisibility
    );

    setColumnVisibility(newColumnVisibility);
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
