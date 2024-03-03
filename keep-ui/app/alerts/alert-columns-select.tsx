import { Table } from "@tanstack/table-core";
import {
  Subtitle,
  MultiSelect,
  MultiSelectItem,
  DateRangePicker,
  DateRangePickerValue,
} from "@tremor/react";
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

  const onMultiSelectChange = (valueKeys: string[]) => {
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

  const onDateRangePickerChange = ({
    from: start,
    to: end,
  }: DateRangePickerValue) => {
    table.setColumnFilters((existingFilters) => {
      // remove any existing "lastReceived" filters
      const filteredArrayFromLastReceived = existingFilters.filter(
        ({ id }) => id !== "lastReceived"
      );

      return filteredArrayFromLastReceived.concat({
        id: "lastReceived",
        value: { start, end },
      });
    });

    table.resetPagination();
  };

  return (
    <div className="grid grid-cols-2 gap-x-2 pt-4">
      <div>
        <Subtitle>Columns</Subtitle>
        <MultiSelect
          value={selectedColumns}
          onValueChange={onMultiSelectChange}
        >
          {columnsOptions.map((column) => (
            <MultiSelectItem key={column} value={column}>
              {column}
            </MultiSelectItem>
          ))}
        </MultiSelect>
      </div>
      <div>
        <Subtitle>Showing alerts from:</Subtitle>
        <DateRangePicker
          onValueChange={onDateRangePickerChange}
          enableYearNavigation
        />
      </div>
    </div>
  );
}
