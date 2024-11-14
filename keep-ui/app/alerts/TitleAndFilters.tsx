import { Table } from "@tanstack/react-table";
import { DateRangePicker, DateRangePickerValue, Title } from "@tremor/react";
import { AlertDto } from "./models";
import ColumnSelection from "./ColumnSelection";
import { ThemeSelection } from "./ThemeSelection";
import EnhancedDateRangePicker from "@/components/ui/DateRangePicker";
import { useState } from "react";

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
  const [timeFrame, setTimeFrame] = useState({
    start: new Date(Date.now() - 24 * 60 * 60 * 1000), // 24 hours ago
    end: new Date(),
    paused: true,
  });

  const handleTimeFrameChange = (newTimeFrame: {
    start: Date;
    end: Date;
    paused?: boolean;
  }) => {
    setTimeFrame(newTimeFrame);

    table.setColumnFilters((existingFilters) => {
      const filteredArrayFromLastReceived = existingFilters.filter(
        ({ id }) => id !== "lastReceived"
      );

      return filteredArrayFromLastReceived.concat({
        id: "lastReceived",
        value: { start: newTimeFrame.start, end: newTimeFrame.end },
      });
    });
    // Force a re-render of the table to update facets
    table.resetRowSelection();
    table.resetPagination();
  };

  return (
    <div className="pt-4 flex justify-between">
      <div className="text-xl">
        <Title className="capitalize inline">{presetName}</Title>
      </div>
      <div className="grid grid-cols-[auto_auto] grid-rows-[auto_auto] gap-4">
        <EnhancedDateRangePicker
          timeFrame={timeFrame}
          setTimeFrame={handleTimeFrameChange}
          hasPlay
          hasRewind
          hasForward
          hasZoomOut
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
