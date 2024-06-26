import { Table } from "@tanstack/react-table";
import { DateRangePicker, DateRangePickerValue, Title } from "@tremor/react";
import { AlertDto } from "./models";
import ColumnSelection from "./ColumnSelection";
import { ThemeSelection } from "./ThemeSelection";

type Theme = {
  [key: string]: string;
};

type TableHeaderProps = {
  presetName: string;
  alerts: AlertDto[];
  table: Table<AlertDto>;
  onThemeChange: (newTheme: Theme) => void;
};

export const TitleAndFilters = ({
  presetName,
  alerts,
  table,
  onThemeChange,
}: TableHeaderProps) => {
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
    <div className="pt-4 flex justify-between">
      <div className="text-xl">
        <Title className="capitalize inline">{presetName}</Title>
      </div>
      <div className="grid grid-cols-[auto_auto] grid-rows-[auto_auto] gap-4">
        <DateRangePicker
          onValueChange={onDateRangePickerChange}
          enableYearNavigation
        />
        <div className="flex items-center">
          <ColumnSelection table={table} presetName={presetName} />
          <ThemeSelection onThemeChange={onThemeChange} />
        </div>
      </div>
    </div>
  );
};
