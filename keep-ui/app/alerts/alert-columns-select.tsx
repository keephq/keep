import { Table } from "@tanstack/table-core";
import { Subtitle, MultiSelect, MultiSelectItem } from "@tremor/react";
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { DEFAULT_COLS, DEFAULT_COLS_VISIBILITY } from "./alert-table-utils";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName: string;
}

export default function AlertColumnsSelect({
  table,
  presetName,
}: AlertColumnsSelectProps) {
  const tableColumns = table.getAllColumns();

  const [, setColumnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    DEFAULT_COLS_VISIBILITY
  );

  const [columnOrder, setColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
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

    const originalColsOrder = columnOrder.filter((columnId) =>
      valueKeys.includes(columnId)
    );
    const newlyAddedCols = valueKeys.filter(
      (columnId) => !columnOrder.includes(columnId)
    );

    const newColumnOrder = [...originalColsOrder, ...newlyAddedCols];

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
