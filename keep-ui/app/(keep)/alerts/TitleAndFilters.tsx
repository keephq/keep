import { Table } from "@tanstack/react-table";
import { Title } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
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
  const [timeFrame, setTimeFrame] = useState<{
    start: Date | null;
    end: Date | null;
    paused: boolean;
    isFromCalendar: boolean;
  }>({
    start: null,
    end: null,
    paused: true,
    isFromCalendar: false,
  });

  const handleTimeFrameChange = (newTimeFrame: {
    start: Date | null;
    end: Date | null;
    paused?: boolean;
    isFromCalendar?: boolean;
  }) => {
    setTimeFrame({
      start: newTimeFrame.start,
      end: newTimeFrame.end,
      paused: newTimeFrame.paused ?? true,
      isFromCalendar: newTimeFrame.isFromCalendar ?? false,
    });

    // Only apply date filter if both start and end dates exist
    if (newTimeFrame.start && newTimeFrame.end) {
      const adjustedTimeFrame = {
        ...newTimeFrame,
        end: new Date(newTimeFrame.end.getTime()),
        paused: newTimeFrame.paused ?? true,
        isFromCalendar: newTimeFrame.isFromCalendar ?? false,
      };

      if (adjustedTimeFrame.isFromCalendar) {
        adjustedTimeFrame.end.setHours(23, 59, 59, 999);
      }

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
    } else {
      // Remove date filter if no dates are selected
      table.setColumnFilters((existingFilters) =>
        existingFilters.filter(({ id }) => id !== "lastReceived")
      );
    }

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
