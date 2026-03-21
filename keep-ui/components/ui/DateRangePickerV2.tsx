import React, { useState, useEffect, useMemo } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Button, Badge, Subtitle, Text } from "@tremor/react";
import { Calendar } from "./Calendar";
import {
  Play,
  Pause,
  FastForward,
  Rewind,
  ZoomOut,
  ChevronRight,
  CalendarIcon,
  ChevronDown,
} from "lucide-react";
import { format } from "date-fns";
import { enUS, zhCN } from "date-fns/locale";
import { type DateRange } from "react-day-picker";
import clsx from "clsx";
import { useI18n } from "@/i18n/hooks/useI18n";
import { useLocale } from "next-intl";

const ONE_MINUTE = 60 * 1000;
const ONE_HOUR = 60 * ONE_MINUTE;
const ONE_DAY = 24 * ONE_HOUR;

export interface AllTimeFrame {
  type: "all-time";
  isPaused: boolean;
}

export interface RelativeTimeFrame {
  type: "relative";
  deltaMs: number;
  isPaused: boolean;
}

export interface AbsoluteTimeFrame {
  type: "absolute";
  start: Date;
  end: Date;
}

export type TimeFrameV2 = AllTimeFrame | RelativeTimeFrame | AbsoluteTimeFrame;

export function areTimeframesEqual(
  first: TimeFrameV2,
  second: TimeFrameV2
): boolean {
  if (first.type !== second.type) {
    return false;
  }

  switch (first.type) {
    case "all-time":
      return first.isPaused === (second as AllTimeFrame).isPaused;
    case "relative": {
      const secondRelative = second as RelativeTimeFrame;
      return (
        first.deltaMs === secondRelative.deltaMs &&
        first.isPaused === secondRelative.isPaused
      );
    }
    case "absolute": {
      const secondAbsolute = second as AbsoluteTimeFrame;
      return (
        first.start.getTime() === secondAbsolute.start.getTime() &&
        first.end.getTime() === secondAbsolute.end.getTime()
      );
    }
  }
}

interface TimePreset {
  badge: string;
  label: string;
  value: () => AbsoluteTimeFrame | RelativeTimeFrame;
}

interface CategoryPreset {
  title: string;
  options: TimePreset[];
}

interface EnhancedDateRangePickerV2Props {
  timeFrame: TimeFrameV2;
  setTimeFrame: (timeFrame: TimeFrameV2) => void;
  className?: string;
  timeframeRefreshInterval?: number;
  disabled?: boolean;
  hasPlay?: boolean;
  hasRewind?: boolean;
  hasForward?: boolean;
  hasZoomOut?: boolean;
  enableYearNavigation?: boolean;
  pausedByDefault?: boolean;
}

export default function EnhancedDateRangePickerV2({
  timeFrame,
  setTimeFrame,
  className = "",
  disabled = false,
  hasPlay = true,
  hasRewind = true,
  hasForward = true,
  hasZoomOut = false,
  pausedByDefault = true,
  enableYearNavigation = false,
}: EnhancedDateRangePickerV2Props) {
  const { t } = useI18n();
  const locale = useLocale();
  const dateFnsLocale = locale === "zh-CN" ? zhCN : enUS;
  const [showCalendar, setShowCalendar] = useState(false);
  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [calendarRange, setCalendarRange] = useState<DateRange | undefined>(
    timeFrame.type === "absolute"
      ? { from: timeFrame.start, to: timeFrame.end }
      : undefined
  );

  const quickPresets = useMemo(
    () =>
      [
        {
          badge: "15m",
          label: t("common.timeRange.past15Minutes"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 15 * ONE_MINUTE,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "1h",
          label: t("common.timeRange.pastHour"),
          value: () =>
            ({
              type: "relative",
              deltaMs: ONE_HOUR,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "4h",
          label: t("common.timeRange.past4Hours"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 4 * ONE_HOUR,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "1d",
          label: t("common.timeRange.pastDay"),
          value: () =>
            ({
              type: "relative",
              deltaMs: ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "2d",
          label: t("common.timeRange.past2Days"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 2 * ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "3d",
          label: t("common.timeRange.past3Days"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 3 * ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "7d",
          label: t("common.timeRange.past7Days"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 7 * ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "15d",
          label: t("common.timeRange.past15Days"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 15 * ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "30d",
          label: t("common.timeRange.past30Days"),
          value: () =>
            ({
              type: "relative",
              deltaMs: 30 * ONE_DAY,
              isPaused: true,
            }) as RelativeTimeFrame,
        },
        {
          badge: "all",
          label: t("common.timeRange.allTime"),
          value: () =>
            ({
              type: "all-time",
              isPaused: true,
            }) as AllTimeFrame,
        },
      ] as TimePreset[],
    [t]
  );

  const categories = useMemo<CategoryPreset[]>(
    () => [
      {
        title: t("common.timeRange.relativeTime"),
        options: [
          {
            badge: "30m",
            label: t("common.timeRange.past30Minutes"),
            value: () => ({
              type: "relative",
              deltaMs: 30 * ONE_MINUTE,
              isPaused: true,
            }),
          },
          {
            badge: "45m",
            label: t("common.timeRange.past45Minutes"),
            value: () => ({
              type: "relative",
              deltaMs: 45 * ONE_MINUTE,
              isPaused: true,
            }),
          },
          {
            badge: "2h",
            label: t("common.timeRange.past2Hours"),
            value: () => ({
              type: "relative",
              deltaMs: 2 * ONE_HOUR,
              isPaused: true,
            }),
          },
          {
            badge: "6h",
            label: t("common.timeRange.past6Hours"),
            value: () => ({
              type: "relative",
              deltaMs: 6 * ONE_HOUR,
              isPaused: true,
            }),
          },
          {
            badge: "6d",
            label: t("common.timeRange.past6Days"),
            value: () => ({
              type: "relative",
              deltaMs: 6 * ONE_DAY,
              isPaused: true,
            }),
          },
          {
            badge: "60d",
            label: t("common.timeRange.past60Days"),
            value: () => ({
              type: "relative",
              deltaMs: 60 * ONE_DAY,
              isPaused: true,
            }),
          },
        ],
      },
      {
        title: t("common.timeRange.fixedTime"),
        options: [
          {
            badge: "today",
            label: t("common.timeRange.today"),
            value: () =>
              ({
                type: "absolute",
                start: new Date(new Date().setHours(0, 0, 0, 0)),
                end: new Date(new Date().setHours(23, 59, 59, 999)),
              }) as AbsoluteTimeFrame,
          },
          {
            badge: "week",
            label: t("common.timeRange.thisWeek"),
            value: () =>
              ({
                type: "absolute",
                start: new Date(new Date().setDate(new Date().getDate() - 7)),
                end: new Date(),
              }) as AbsoluteTimeFrame,
          },
        ],
      },
    ],
    [t]
  );

  const relativePresetsMapped = useMemo(() => {
    return categories
      .flatMap((categoryPreset) => categoryPreset.options)
      .filter((timePreset) => timePreset.value().type === "relative")
      .concat(quickPresets)
      .reduce(
        (result, current) =>
          result.set((current.value() as RelativeTimeFrame).deltaMs, current),
        new Map<number, TimePreset>()
      );
  }, [quickPresets, categories]);

  const handlePresetSelect = (preset: TimePreset, isPaused = true) => {
    setTimeFrame(preset.value());
    setIsOpen(false);
    setSelectedCategory(null);
    setShowMoreOptions(false);
    setCalendarRange(undefined);
  };

  const togglePlayPause = () => {
    const current = timeFrame as RelativeTimeFrame | AllTimeFrame;
    setTimeFrame({ ...current, isPaused: !current.isPaused } as any);
  };

  const handleRewind = () => {
    // TODO: Implement the rewind functionality
  };

  const handleForward = () => {
    // TODO: Implement the forward functionality
  };

  const handleZoomOut = () => {
    // TODO: Implement the zoom out functionality
  };

  useEffect(() => {
    if (!isOpen) {
      setShowCalendar(false);
      setShowMoreOptions(false);
      setSelectedCategory(null);
    }
  }, [isOpen]);

  const formatDuration = (start: Date, end: Date): string => {
    const durationMs = end.getTime() - start.getTime();
    const days = Math.floor(durationMs / (24 * 60 * 60 * 1000));
    const hours = Math.floor(
      (durationMs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000)
    );
    const minutes = Math.floor((durationMs % (60 * 60 * 1000)) / (60 * 1000));

    if (days > 0) {
      return `${days}d`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else {
      return `${minutes}m`;
    }
  };

  const selectedTimeFrameInfo = useMemo(() => {
    switch (timeFrame.type) {
      case "relative": {
        const timePreset = relativePresetsMapped.get(timeFrame.deltaMs);
        let optionText = timePreset?.label || t("common.timeRange.custom");
        let badgeText = timePreset?.badge || t("common.timeRange.custom");

        if (!timeFrame.isPaused) {
          badgeText = t("common.timeRange.live");
        }

        return { badgeText, optionText };
      }

      case "absolute":
        const absoluteTimeFrame = timeFrame as AbsoluteTimeFrame;
        return {
          badgeText: formatDuration(
            absoluteTimeFrame.start,
            absoluteTimeFrame.end
          ),
          optionText: `${format(absoluteTimeFrame.start, "MMM d, yyyy HH:mm", {
            locale: dateFnsLocale,
          })} - ${format(absoluteTimeFrame.end, "MMM d, yyyy HH:mm", {
            locale: dateFnsLocale,
          })}`,
        };
      case "all-time":
        return {
          badgeText: t("common.timeRange.all"),
          optionText: t("common.timeRange.allTime"),
        };
    }
  }, [dateFnsLocale, relativePresetsMapped, t, timeFrame]);

  const handleCalendarSelect = (date: DateRange | Date | undefined) => {
    setCalendarRange(undefined);

    if (date && "from" in date) {
      setCalendarRange(date);
      if (date.from && date.to && date.from.getTime() !== date.to.getTime()) {
        setTimeFrame({
          type: "absolute",
          start: date.from,
          end: date.to,
        } as AbsoluteTimeFrame);
        setIsOpen(false);
        setShowCalendar(false);
      }
    }
  };

  return (
    <div className="flex items-center">
      <Popover.Root open={isOpen} onOpenChange={setIsOpen}>
        <Popover.Trigger asChild>
          <Button
            data-testid="timeframe-picker-trigger"
            size="xs"
            variant="secondary"
            className={clsx(
              "justify-start rounded border-b border-gray-200 hover:bg-gray-200",
              isOpen && "rounded-b-none"
            )}
            disabled={disabled}
          >
            <div className="flex items-center w-full">
              <Badge
                color={
                  "isPaused" in timeFrame && !(timeFrame as any).isPaused
                    ? "green"
                    : "gray"
                }
                className={`mr-2 min-w-14 justify-center ${
                  "isPaused" in timeFrame && !(timeFrame as any).isPaused
                    ? "bg-green-700"
                    : ""
                }`}
              >
                {selectedTimeFrameInfo.badgeText}
              </Badge>
              <span className="text-gray-900 text-left translate-y-[1px] min-w-[300px]">
                <Text>{selectedTimeFrameInfo.optionText}</Text>
              </span>
              <ChevronDown className="w-4 h-4 ml-auto text-gray-500" />
            </div>
          </Button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            data-testid="timeframe-picker-content"
            className="z-50 w-[var(--radix-popover-trigger-width)] -mt-px rounded-md rounded-t-none border bg-white shadow-md outline-none"
            align="start"
          >
            {!showCalendar ? (
              <div className="p-0 w-full relative">
                <div className="flex flex-col">
                  {quickPresets.map((preset, index) => (
                    <Button
                      key={index}
                      variant="secondary"
                      className="w-full justify-start rounded-none border-transparent first:rounded-t h-8 hover:bg-gray-200 px-2"
                      onClick={() => handlePresetSelect(preset)}
                    >
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center text-sm"
                      >
                        {preset.badge}
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {preset.label}
                      </span>
                    </Button>
                  ))}

                  <Button
                    variant="secondary"
                    className="w-full justify-start rounded-none border-transparent h-8 hover:bg-gray-200 px-2"
                    onClick={() => setShowCalendar(true)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center"
                      >
                        <CalendarIcon size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {t("common.timeRange.selectFromCalendar")}
                      </span>
                    </div>
                  </Button>

                  <Button
                    variant="secondary"
                    className="w-full justify-start rounded-none border-transparent last:rounded-b h-8 hover:bg-gray-200 px-2"
                    onClick={() => setShowMoreOptions(!showMoreOptions)}
                  >
                    <div className="flex items-center w-full">
                      <Badge
                        color="gray"
                        className="mr-2 min-w-14 justify-center"
                      >
                        <ChevronRight size={16} />
                      </Badge>
                      <span className="text-gray-900 text-sm">
                        {t("common.timeRange.moreOptions")}
                      </span>
                    </div>
                  </Button>
                </div>

                {showMoreOptions && (
                  <div className="absolute right-full top-0 w-64 border bg-white shadow-md">
                    {categories.map((category, index) => (
                      <div key={index} className="p-3">
                        <Subtitle className="text-xs text-gray-500 font-medium mb-2">
                          {category.title}
                        </Subtitle>
                        <div className="flex flex-wrap gap-1.5">
                          {category.options.map((option, optionIndex) => (
                            <Badge
                              key={optionIndex}
                              color="gray"
                              className="cursor-pointer transition-colors text-sm"
                              onClick={() => handlePresetSelect(option)}
                            >
                              {option.badge}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 z-50">
                <Calendar
                  mode="range"
                  selected={calendarRange}
                  onSelect={handleCalendarSelect}
                  numberOfMonths={1}
                  disabled={{ after: new Date() }}
                  className="w-full bg-white"
                  defaultMonth={
                    timeFrame.type === "absolute"
                      ? new Date(timeFrame.start)
                      : undefined
                  }
                />
              </div>
            )}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>

      <div className="flex items-center relative z-0 gap-x-2 ml-2 h-full">
        <div className="flex h-full">
          {hasPlay &&
            (timeFrame.type === "relative" ||
              timeFrame.type === "all-time") && (
              <Button
                size="xs"
                color="gray"
                variant="secondary"
                className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200 h-full"
                onClick={togglePlayPause}
                disabled={disabled}
                icon={timeFrame.isPaused ? Play : Pause}
              />
            )}

          {hasRewind && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
              onClick={handleRewind}
              disabled={disabled}
              icon={Rewind}
            />
          )}

          {hasForward && (
            <Button
              size="xs"
              color="gray"
              variant="secondary"
              className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
              onClick={handleForward}
              disabled={disabled}
              icon={FastForward}
            />
          )}
        </div>

        {hasZoomOut && (
          <Button
            size="xs"
            color="gray"
            variant="secondary"
            className="justify-start rounded-none first:rounded-l last:rounded-r border-b border-gray-200"
            onClick={handleZoomOut}
            disabled={disabled}
            icon={ZoomOut}
          />
        )}
      </div>
    </div>
  );
}
