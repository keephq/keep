import { Table } from "@tanstack/react-table";
import { DateRangePicker, DateRangePickerValue, Title } from "@tremor/react";
import { AlertDto } from "./models";
import ColumnSelection from "./ColumnSelection";
import { LastRecieved } from "./LastReceived";

type TableHeaderProps = {
  presetName: string;
  alerts: AlertDto[];
  table: Table<AlertDto>;
};

export const TitleAndFilters = ({
  presetName,
  alerts,
  table,
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
    <div className="flex justify-between">
      <div className="pt-4 text-xl">
        <Title className="capitalize inline">{presetName}</Title>{" "}
        <span className="text-gray-400">({alerts.length})</span>
      </div>

      <div className="grid grid-cols-[auto_auto] grid-rows-[auto_auto] gap-4">
        <DateRangePicker
          onValueChange={onDateRangePickerChange}
          enableYearNavigation
        />
        <ColumnSelection table={table} presetName={presetName} />
        <LastRecieved />
      </div>
    </div>
  );
};
