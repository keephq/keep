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
    start: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), // 365 days ago
    end: new Date(), // now
    paused: true,
    isFromCalendar: false,
  });

  const handleTimeFrameChange = (newTimeFrame: {
    start: Date;
    end: Date;
    paused?: boolean;
    isFromCalendar?: boolean;
  }) => {
    // Create a new end date that includes the full day
    const adjustedTimeFrame = {
      ...newTimeFrame,
      end: new Date(newTimeFrame.end.getTime()),
      paused: newTimeFrame.paused ?? true, // Provide default value if undefined
      isFromCalendar: newTimeFrame.isFromCalendar ?? false,
    };
    if (adjustedTimeFrame.isFromCalendar) {
      adjustedTimeFrame.end.setHours(23, 59, 59, 999);
    }

    setTimeFrame(adjustedTimeFrame);

    table.setColumnFilters((existingFilters) => {
      const filteredArrayFromLastReceived = existingFilters.filter(
        ({ id }) => id !== "lastReceived"
      );

      return filteredArrayFromLastReceived.concat({
        id: "lastReceived",
        value: {
          start: adjustedTimeFrame.start,
          end: adjustedTimeFrame.end,
        },
      });
    });

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
          hasPlay={false}
          hasRewind={false}
          hasForward={false}
          hasZoomOut={false}
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
