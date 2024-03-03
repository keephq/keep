import { Table } from "@tanstack/table-core";
import {
  Subtitle,
  MultiSelect,
  MultiSelectItem,
  Select,
  SelectItem,
} from "@tremor/react";
import { AlertDto } from "./models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import {
  VisibilityState,
  ColumnOrderState,
  FilterFn,
} from "@tanstack/react-table";
import { DEFAULT_COLS, DEFAULT_COLS_VISIBILITY } from "./alert-table-utils";
import { isValid, isWithinInterval, sub } from "date-fns";

export const isDateWithinRange: FilterFn<AlertDto> = (row, columnId, value) => {
  const date = new Date(row.getValue(columnId));

  const { start, end } = value;

  if (isValid(start) && isValid(end)) {
    return isWithinInterval(date, { start: end, end: start });
  }

  return true;
};

const TIME_RANGE_VALUES = {
  "All time": () => [],
  "1 hour": () => ({ start: new Date(), end: sub(new Date(), { hours: 1 }) }),
  "1 day": () => ({ start: new Date(), end: sub(new Date(), { days: 1 }) }),
  "1 week": () => ({ start: new Date(), end: sub(new Date(), { weeks: 1 }) }),
  "1 month": () => ({ start: new Date(), end: sub(new Date(), { months: 1 }) }),
} as const;

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

  const onTimeRangeSelectChange = (selectedTime: string) => {
    const selectedOption =
      TIME_RANGE_VALUES[selectedTime as keyof typeof TIME_RANGE_VALUES]();

    return table.setColumnFilters((existingFilters) => {
      const filteredArrayFromLastReceived = existingFilters.filter(
        ({ id }) => id !== "lastReceived"
      );

      return filteredArrayFromLastReceived.concat({
        id: "lastReceived",
        value: selectedOption,
      });
    });
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
        <Select defaultValue="All time" onValueChange={onTimeRangeSelectChange}>
          {Object.keys(TIME_RANGE_VALUES).map((time) => (
            <SelectItem key={time} value={time}>
              {time}
            </SelectItem>
          ))}
        </Select>
      </div>
    </div>
  );
}
