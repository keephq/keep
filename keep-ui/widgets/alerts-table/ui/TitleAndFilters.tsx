import { Table } from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";
import SettingsSelection from "@/widgets/alerts-table/ui/SettingsSelection";
import EnhancedDateRangePicker, {
  TimeFrame,
} from "@/components/ui/DateRangePicker";
import { useEffect, useState } from "react";
import { PageTitle } from "@/shared/ui";

type TableHeaderProps = {
  presetName: string;
  alerts: AlertDto[];
  table: Table<AlertDto>;
  liveUpdateOptionEnabled?: boolean;
  timeframeRefreshInterval?: number;
  onTimeframeChange?: (timeFrame: TimeFrame | null) => void;
};

export const TitleAndFilters = ({
  presetName,
  table,
  liveUpdateOptionEnabled = false,
  timeframeRefreshInterval = 1000,
  onTimeframeChange,
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

  useEffect(() => {
    if (onTimeframeChange) {
      onTimeframeChange(timeFrame);
    }
  }, [timeFrame, onTimeframeChange]);

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

    // We don't need to manipulate table in case onDateRange is provided.
    // Most likely the code below must be removed in the future.
    if (onTimeframeChange) {
      return;
    }

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
    <div className="flex justify-between">
      <PageTitle className="capitalize inline">{presetName}</PageTitle>
      <div className="grid grid-cols-[auto_auto] grid-rows-[auto_auto] gap-4">
        <EnhancedDateRangePicker
          timeFrame={timeFrame}
          setTimeFrame={handleTimeFrameChange}
          timeframeRefreshInterval={timeframeRefreshInterval}
          hasPlay={liveUpdateOptionEnabled}
          pausedByDefault={liveUpdateOptionEnabled}
          hasRewind={false}
          hasForward={false}
          hasZoomOut={false}
          enableYearNavigation
        />
        <div className="flex items-center">
          <SettingsSelection table={table} presetName={presetName} />
        </div>
      </div>
    </div>
  );
};
