import { Table } from "@tanstack/table-core";
import { Subtitle, MultiSelect, MultiSelectItem } from "@tremor/react";
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { getDefaultColumnVisibilityState } from "./alert-table-utils";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName: string;
  columnsIds: string[];
}

export default function AlertColumnsSelect({
  table,
  presetName,
  columnsIds,
}: AlertColumnsSelectProps) {
  const tableColumns = table.getAllColumns();

  const [, setColumnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    getDefaultColumnVisibilityState(columnsIds)
  );

  const [, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    columnsIds
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
      {}
    );

    const newColumnOrder = columnsOptions.reduce<ColumnOrderState>(
      (acc, columnId) => {
        if (valueKeys.includes(columnId)) {
          return acc.concat(columnId);
        }

        return acc;
      },
      []
    );

    setColumnVisibility(newColumnVisibility);
    setColumnOrder(newColumnOrder);
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
